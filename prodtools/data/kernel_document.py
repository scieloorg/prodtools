import copy
import logging
import sqlite3

from typing import Optional

from lxml import etree  # type: ignore

from prodtools.utils import fs_utils
from prodtools.utils import xml_utils
from prodtools.db.pid_versions import PIDVersionsManager
from . import scielo_id_gen

LOGGER = logging.getLogger(__name__)


def add_article_id_to_received_documents(
    pid_manager: PIDVersionsManager,
    issn_id: str,
    year_and_order: str,
    received_docs: dict,
    documents_in_isis: dict,
    file_paths: dict,
    update_article_with_aop_status: callable,
) -> None:
    """Atualiza article-id (scielo-v2 e scielo-v3) dos documentos recebidos.

    Params:
        pid_manager (PIDVersionsManager): instância de PIDVersionsManager para gerir pid da versão 3
        issn_id (str): ISSN do periódico
        year_and_order (str): Ano e ordem da issue processada
        received_docs (dict): Pacote de documentos recebidos para processar
        documents_in_isis (dict): Documentos já registrados na base isis (acron/volnum)
        file_paths (dict): arquivos do received_docs
        update_article_with_aop_status (callable): Função que recupera o AOP PID e modifica o
            artigo com este dado

    Returns:
        None
    """

    for xml_name, article in received_docs.items():
        # Atribui `previous_pid` da base AOP (`article.registered_aop_pid`)
        update_article_with_aop_status(article)
        pids_to_append_in_xml = new_register_pids_in_pid_manager(
            pid_manager, article, issn_id, year_and_order)
        update_article_xml_file_with_pids(
            file_paths.get(xml_name), pids_to_append_in_xml)


def get_scielo_pid_v2(issn_id, year_and_order, order_in_issue):
    year = year_and_order[:4]
    order_in_year = year_and_order[4:].zfill(4)
    return "".join(("S", issn_id, year, order_in_year, order_in_issue))


def add_article_id_to_etree(
    tree: etree.ElementTree, pid_and_specific_use_items: list
) -> Optional[etree.ElementTree]:
    """Adiciona os pids v2 e v3 a árvore lxml de um documento"""
    if (
        tree is None
        or pid_and_specific_use_items is None
        or len(pid_and_specific_use_items) == 0
    ):
        return None

    _tree = copy.deepcopy(tree)

    article_meta = _tree.find(".//article-meta")

    if article_meta is None:
        LOGGER.debug(
            "Could not insert articles ids because the article-meta isn't found"
        )
        return None

    for specific_use, id_value in pid_and_specific_use_items.items():
        if not id_value:
            continue
        node = article_meta.find(
                ".//article-meta[@specific_use='{}']".format(specific_use))
        if node is not None and node.text != id_value:
            continue
        article_id = etree.Element("article-id")
        article_id.text = id_value
        article_id.set("specific-use", specific_use)
        article_id.set("pub-id-type", "publisher-id")
        article_meta.insert(0, article_id)

    return _tree


def write_etree_to_file(tree: etree.ElementTree, path: str) -> None:
    """Escreve uma árvore lxml em um arquivo de destino. Também
    garante que as entidades não serão modificadas por meio da função
    xml_utils.tostring(etree)."""

    if tree is None or path is None:
        return None

    fs_utils.write_file(path, xml_utils.tostring(tree))


def update_article_xml_file_with_pids(file_path, pids_to_append_in_xml):
    if not pids_to_append_in_xml:
        return
    if not file_path:
        return
    try:
        tree = xml_utils.get_xml_object(file_path)
    except xml_utils.etree.XMLSyntaxError:
        LOGGER.info("%s is not a valid XML", file_path)
    else:
        _tree = add_article_id_to_etree(tree, pids_to_append_in_xml)
        write_etree_to_file(_tree, file_path)


def old_register_pids_in_pid_manager(pid_manager, article, issn_id, year_and_order):
    pid_v2 = article.get_scielo_pid("v2")
    pid_v3 = article.get_scielo_pid("v3")
    pids_to_append_in_xml = []

    if pid_v2 and pid_v3:
        exists_in_database = pid_manager.pids_already_registered(pid_v2, pid_v3)

        if not exists_in_database:
            pid_manager.register(pid_v2, pid_v3)

        return pids_to_append_in_xml

    if pid_v2 is None:
        pid_v2 = get_scielo_pid_v2(issn_id, year_and_order, article.order)
        pids_to_append_in_xml.append((pid_v2, "scielo-v2"))

    if pid_v3 is None:
        pid_v3 = (
            pid_manager.get_pid_v3(article.registered_aop_pid)
            or pid_manager.get_pid_v3(pid_v2)
            or scielo_id_gen.generate_scielo_pid()
        )
        article.registered_scielo_id = pid_v3
        pids_to_append_in_xml.append((pid_v3, "scielo-v3"))

    try:
        pid_manager.register(pid_v2, pid_v3)
    except sqlite3.OperationalError:
        LOGGER.exception(
            "Could not update sql database with pid v2 and v3."
            " The following exception was captured."
        )
    return pids_to_append_in_xml


def new_register_pids_in_pid_manager(pid_manager, article, issn_id, year_and_order):
    pids_to_append_in_xml = {}

    previous_pid = article.registered_aop_pid

    # anota para ser incluído no XML
    pids_to_append_in_xml["previous-pid"] = previous_pid

    # v2
    pid_v2 = article.get_scielo_pid("v2")
    if pid_v2 is None:
        pid_v2 = get_scielo_pid_v2(issn_id, year_and_order, article.order)
        # anota para ser incluído no XML
    pids_to_append_in_xml["scielo-v2"] = pid_v2

    # v3
    pid_v3 = article.get_scielo_pid("v3")
    pids_to_append_in_xml["scielo-v3"] = pid_v3
    
    # manage
    result = pid_manager.manage(
        pid_v2, pid_v3, previous_pid, scielo_id_gen.generate_scielo_pid,
    )
    if result:
        v2, v3, prev = result
        article.registered_scielo_id = v3
        pids_to_append_in_xml["scielo-v3"] = v3

    return pids_to_append_in_xml


import os
import copy
import logging

from typing import Optional

from lxml import etree  # type: ignore
from scielo_v3_manager.pid_manager import Manager
from scielo_v3_manager.v3_gen import generates

from prodtools.utils import fs_utils
from prodtools.utils import xml_utils

LOGGER = logging.getLogger(__name__)


class PidManagerExceedsIntentTimesError(Exception):
    ...


def update_xml_file(file_path, pids_to_append_in_xml):
    if not pids_to_append_in_xml:
        # nada para atualizar
        return None
    if not file_path:
        LOGGER.debug("Could not find XML path")
        return None
    try:
        tree = xml_utils.get_xml_object(file_path)
    except xml_utils.etree.XMLSyntaxError:
        LOGGER.info("%s is not a valid XML", file_path)
    else:
        # atualizar XML com os `pids_to_append_in_xml`
        _tree = add_article_id_to_etree(tree, pids_to_append_in_xml)
        write_etree_to_file(_tree, file_path)


def add_article_id_to_received_documents(
    pid_manager_info: dict,
    issn_id: str,
    year_and_order: str,
    received_docs: dict,
    documents_in_isis: dict,
    file_paths: dict,
    update_article_with_aop_status: callable,
) -> None:

    exceptions = []
    registered_v3_items = {}
    total = len(received_docs)
    times = 0
    MAX_TRIES = total
    results = {}
    while True:
        try:
            pid_manager = Manager(
                pid_manager_info['name'], pid_manager_info['timeout'])
            _add_article_id_to_received_documents(
                pid_manager,
                issn_id,
                year_and_order,
                received_docs,
                documents_in_isis,
                file_paths,
                update_article_with_aop_status,
                registered_v3_items,
                results,
            )
        except Exception as e:
            exceptions.append(str(e))
        finally:
            done = len([v for v in registered_v3_items.values() if v])
            if done == total:
                break
            times += 1
            if times > MAX_TRIES or len(exceptions) > 0:
                raise PidManagerExceedsIntentTimesError(
                    "Pid Manager failed to set v3 to %i documents. "
                    "Tried %i times. "
                    "Done for %i documents. %s %s" %
                    (total, times, done, results, "\n".join(exceptions))
                )


def _add_article_id_to_received_documents(
    pid_manager: Manager,
    issn_id: str,
    year_and_order: str,
    received_docs: dict,
    documents_in_isis: dict,
    file_paths: dict,
    update_article_with_aop_status: callable,
    registered_v3_items: dict,
    results: dict,
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
        if registered_v3_items.get(xml_name):
            continue
        file_path = file_paths.get(xml_name)
        if not file_path:
            LOGGER.debug("Could not find XML path for '%s' xml.", xml_name)

        pids_to_append_in_xml = []

        # Obtém v2 do XML
        pid_v2 = article.get_scielo_pid("v2")
        if pid_v2 is None:
            # se v2 não está presente no XML, gerar a partir dos metadados
            pid_v2 = get_scielo_pid_v2(issn_id, year_and_order, article.order)
            # anotar para ser inserido no XML
            pids_to_append_in_xml.append((pid_v2, "scielo-v2"))

        # Obtém v3 do XML
        pid_v3 = article.get_scielo_pid("v3")

        # Obtém previous do XML
        prev_pid = article.previous_article_pid
        if not prev_pid:
            # Não há previous do XML
            # Obtém previous_pid registrado na base ahead do artigo
            if update_article_with_aop_status:
                update_article_with_aop_status(article)
            # acessa previous_pid com `article.registered_aop_pid`
            prev_pid = article.registered_aop_pid
            if prev_pid:
                pids_to_append_in_xml.append((prev_pid, "previous-pid"))

        # consulta / registra / atualiza os dados na base pid_manager
        result = pid_manager.manage(
            v2=pid_v2, v3=pid_v3, aop=prev_pid,
            filename=os.path.basename(file_path),
            doi=article.doi,
            status="",
            generate_v3=generates)
        results[xml_name] = result

        v3 = result.get("saved", {}).get("v3")
        if v3:
            registered_v3_items[xml_name] = v3

        if pid_v3 is None:
            # se v3 não está no presente no XML
            article.registered_scielo_id = v3
            # anotar para ser inserido no XML
            pids_to_append_in_xml.append((v3, "scielo-v3"))

        # atualizar o XML com pids_to_append_in_xml
        update_xml_file(file_path, pids_to_append_in_xml)


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

    for id_value, specific_use in pid_and_specific_use_items:
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

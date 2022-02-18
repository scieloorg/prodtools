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
        _tree = update_article_id_in_xml(tree, pids_to_append_in_xml)
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

        response = _get_pids_to_append_in_xml(
            pid_manager, article, issn_id, year_and_order,
            file_path,
            update_article_with_aop_status,
        )

        results[xml_name] = response['pid_manager_result']
        registered_v3_items[xml_name] = response['registered_v3']
        pids_to_append_in_xml = response['pids_to_append_in_xml']

        # atualizar o XML com pids_to_append_in_xml
        update_xml_file(file_path, pids_to_append_in_xml)


def _migrate_pid_v2_to_previous_pid(pids_to_append_in_xml, record, pid_v2, prev_pid):
    if record and not prev_pid:
        # artigo não tem previous pid

        # recupera previous pid do pid_manager
        recovered_aop_pid = record.get("aop")
        if not recovered_aop_pid:
            # não há previous pid no pid_manager, mas
            # como o v2 recuperado do pid_manager é diferente do v2 do xml
            # ele deve ser o previous-pid
            if record.get("v2") and pid_v2 and pid_v2 != record.get("v2"):
                recovered_aop_pid = record.get("v2")
        if recovered_aop_pid:
            # se há previous-pid, atualiza o XML com previous-pid
            pids_to_append_in_xml.append(
                (recovered_aop_pid, "previous-pid"))


def _update_pid_values_with_values_registered_in_pid_manager(
        pids_to_append_in_xml, record, pid_v2, prev_pid):
    """
    Os valores recuperados são mais confiávies, pois foram obtidos
    dos registros da base de dados que guardam outros dados para a comparação /
    validação
    """
    if not record:
        return

    items = [
        ("scielo-v2", record.get("v2"), pid_v2),
        ("previous-pid", record.get("aop"), prev_pid),
    ]
    for specific_use, registered_value, original_value in items:
        if registered_value != original_value:
            pids_to_append_in_xml.append(
                (registered_value, specific_use)
            )


def _get_pid_v2(pids_to_append_in_xml, article, issn_id, year_and_order):
    # Obtém v2 do XML
    pid_v2 = article.get_scielo_pid("v2")
    if pid_v2 is None:
        # se v2 não está presente no XML, gerar a partir dos metadados
        pid_v2 = build_scielo_pid_v2(issn_id, year_and_order, article.order)
        # anotar para ser inserido no XML
        pids_to_append_in_xml.append((pid_v2, "scielo-v2"))
    return pid_v2


def _get_previous_pid_v2(pids_to_append_in_xml, article, update_article_with_aop_status):
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
    return prev_pid


def _get_pid_v3(pids_to_append_in_xml, article, pid_manager_v3):
    # Obtém v3 do XML
    pid_v3 = article.get_scielo_pid("v3")

    if pid_manager_v3:
        # se v3 não está no presente no XML
        article.registered_scielo_id = pid_manager_v3
        pid_v3 = pid_manager_v3
        # anotar para ser inserido no XML
        pids_to_append_in_xml.append((pid_manager_v3, "scielo-v3"))

    return pid_v3


def _get_pids_to_append_in_xml(pid_manager, article, issn_id, year_and_order,
                               file_path,
                               update_article_with_aop_status,
                               ):

    pids_to_append_in_xml = []

    # Obtém v2 do XML
    pid_v2 = _get_pid_v2(pids_to_append_in_xml, article,
                         issn_id, year_and_order)

    # Obtém previous do XML
    prev_pid = _get_previous_pid_v2(pids_to_append_in_xml, article,
                                    update_article_with_aop_status)

    # Obtém v3 do XML
    pid_v3 = article.get_scielo_pid("v3")

    # consulta / registra / atualiza os dados na base pid_manager
    result = pid_manager.manage(
        v2=pid_v2, v3=pid_v3, aop=prev_pid,
        filename=os.path.basename(file_path),
        doi=article.doi,
        status="",
        generate_v3=generates)

    record = result.get("saved") or result.get("registered") or {}

    registered_v3 = (
        _get_pid_v3(pids_to_append_in_xml, article, record.get("v3"))
    )

    # atualiza aop pid, se aplicável
    print(pids_to_append_in_xml, record, pid_v2, prev_pid)
    _migrate_pid_v2_to_previous_pid(
        pids_to_append_in_xml, record, pid_v2, prev_pid
    )

    return {
        "pid_manager_result": result,
        "pids_to_append_in_xml": pids_to_append_in_xml,
        "registered_v3": registered_v3
    }


def build_scielo_pid_v2(issn_id, year_and_order, order_in_issue):
    year = year_and_order[:4]
    order_in_year = year_and_order[4:].zfill(4)
    return "".join(("S", issn_id, year, order_in_year, order_in_issue))


def update_article_id_in_xml(
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
        node = article_meta.find(f".//article-id[@specific-use='{specific_use}']")

        if id_value and node is None:
            article_id = etree.Element("article-id")
            article_id.text = id_value
            article_id.set("specific-use", specific_use)
            article_id.set("pub-id-type", "publisher-id")
            article_meta.insert(0, article_id)
        elif id_value:
            node.text = id_value
        elif node is not None:
            article_meta.remove(node)

    return _tree


def write_etree_to_file(tree: etree.ElementTree, path: str) -> None:
    """Escreve uma árvore lxml em um arquivo de destino. Também
    garante que as entidades não serão modificadas por meio da função
    xml_utils.tostring(etree)."""

    if tree is None or path is None:
        return None

    fs_utils.write_file(path, xml_utils.tostring(tree))

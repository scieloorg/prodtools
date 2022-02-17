# coding:utf-8
import tempfile
import unittest
from unittest.mock import Mock, patch
import os

from io import StringIO

from lxml import etree
from copy import deepcopy
from prodtools.data import spf_document


def mock_update_article_with_aop_status(article):
    article.registered_aop_pid = "saved_in_isis"


class MockArticle:
    def __init__(self, pid_v3=None, pid_v2=None, db_prev_pid=None, prev_pid=None):
        # este atributo não existe no Article real
        self._scielo_pid = pid_v2

        # estes atributos existem no Article real
        self.scielo_id = pid_v3
        self.registered_scielo_id = None
        self.registered_aop_pid = db_prev_pid
        self.previous_article_pid = prev_pid
        self.order = "12345"
        self.doi = ""

    def get_scielo_pid(self, name):
        # simula o get_scielo_pid real
        if name == "v3":
            return self.scielo_id
        return self._scielo_pid


class TestSPFDocumentAddArticleIdToReceivedDocuments(unittest.TestCase):
    def setUp(self):
        self.files = ["file" + str(i) + ".xml" for i in range(1, 6)]
        for f in self.files:
            with open(f, "wb") as fp:
                fp.write(b"<article><article-meta></article-meta></article>")

    def tearDown(self):
        for f in self.files:
            try:
                os.unlink(f)
            except IOError:
                pass

    def _return_scielo_pid_v3_if_aop_pid_match(self, prev_pid, pid):
        """Representa a busca pelo PID v3 a partir do PID v2"""
        if prev_pid == "AOPPID":
            return "pid-v3-registrado-anteriormente-para-documento-aop"
        return "brzWFrVFdpYMXdpvq7dDJBQ"


class TestSPFDocumentWriteFile(unittest.TestCase):

    def setUp(self):

        self.tree = etree.parse(
            StringIO(
                """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">
                    <article>
                        <article-meta>
                            <field>São Paulo - É, ê, È, ç</field>
                        </article-meta>
                    </article>
                """
            ),
            etree.XMLParser(),
        )

    def test_add_pids_to_etree_should_return_none_if_etree_is_not_valid(self):
        self.assertIsNone(spf_document.add_article_id_to_etree(None, []))

    def test_add_pids_to_etree_should_not_update_if_pid_list_is_empty(self):
        tree = etree.fromstring("<article><article-meta></article-meta></article>")
        self.assertIsNone(spf_document.add_article_id_to_etree(tree, []))

    def test_add_pids_to_etree_should_etree_with_pid_v3(self):
        tree = etree.fromstring(
            """<article>
                <article-meta></article-meta>
            </article>"""
        )
        _tree = spf_document.add_article_id_to_etree(
            tree, [("random-pid", "pid-v3",)]
        )
        self.assertIn(
            b'<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            etree.tostring(_tree),
        )

    def test_add_pids_to_etree_should_not_modify_the_documents_doctype(self):
        _tree = spf_document.add_article_id_to_etree(
            self.tree, [("random-pid", "pid-v3",)]
        )
        self.assertIn(
            b"""<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">""",
            etree.tostring(_tree),
        )

    def test_write_etree_to_file_should_not_update_file_if_etree_is_none(self):
        temporary_file = tempfile.mktemp()
        spf_document.write_etree_to_file(None, path=temporary_file)
        self.assertFalse(os.path.exists(temporary_file))

    def test_write_etree_to_file_should_not_convert_character_to_entity(self):
        tree = etree.fromstring(
            """<article>
                <article-meta>
                    <field>São Paulo - É, ê, È, ç</field>
                </article-meta>
            </article>"""
        )
        temporary_file = tempfile.mktemp()
        spf_document.write_etree_to_file(tree, path=temporary_file)

        with open(temporary_file, "r") as f:
            self.assertIn("São Paulo - É, ê, È, ç", f.read())

    def test_write_etree_to_file_should_not_change_the_document_doctype(self):
        temporary_file = tempfile.mktemp()
        spf_document.write_etree_to_file(self.tree, path=temporary_file)

        with open(temporary_file, "r") as f:
            self.assertIn(
                """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">""",
                f.read(),
            )


class TestSPFDocumentBuildPidV2(unittest.TestCase):

    def test_build_scielo_pid_v2(self):
        result = spf_document.build_scielo_pid_v2(
            issn_id="3456-0987",
            year_and_order="20095",
            order_in_issue="54321")
        self.assertEqual("S3456-09872009000554321", result)


class TestSPFDocumentGetPidV2(unittest.TestCase):

    def test__get_pid_v2__returns_pid_in_xml(self):
        pids_to_append_in_xml = []

        pid_in_xml = "S3456-09872009000554321"
        mock_article = MockArticle(
            pid_v3="naoimporta",
            pid_v2=pid_in_xml,
        )

        result = spf_document._get_pid_v2(
            pids_to_append_in_xml,
            mock_article,
            issn_id="3456-0987",
            year_and_order="20095"
        )
        self.assertEqual(pid_in_xml, result)
        self.assertEqual([], pids_to_append_in_xml)

    def test__get_pid_v2__returns_built_pid(self):
        pids_to_append_in_xml = []
        mock_article = MockArticle(
            pid_v3="naoimporta",
            pid_v2=None,
        )

        result = spf_document._get_pid_v2(
            pids_to_append_in_xml,
            mock_article,
            issn_id="3456-0987",
            year_and_order="200913"
        )
        self.assertEqual("S3456-09872009001312345", result)
        self.assertEqual(
            [("S3456-09872009001312345", "scielo-v2")],
            pids_to_append_in_xml
        )


class TestSPFDocumentGetPreviousPidV2(unittest.TestCase):

    def test__get_previous_pid_v2__returns_pid_in_xml(self):
        pids_to_append_in_xml = []

        in_xml = "S3456-09872009000554321"
        mock_article = MockArticle(prev_pid=in_xml)

        result = spf_document._get_previous_pid_v2(
            pids_to_append_in_xml,
            mock_article,
            mock_update_article_with_aop_status,
        )

        self.assertEqual(in_xml, result)
        self.assertEqual([], pids_to_append_in_xml)

    def test__get_previous_pid_v2__returns_got_from_db(self):
        pids_to_append_in_xml = [("xxx", "scielo-v2")]
        mock_article = MockArticle()

        result = spf_document._get_previous_pid_v2(
            pids_to_append_in_xml,
            mock_article,
            mock_update_article_with_aop_status,
        )
        self.assertEqual("saved_in_isis", result)
        self.assertEqual(
            [("xxx", "scielo-v2"),
             ("saved_in_isis", "previous-pid")],
            pids_to_append_in_xml
        )

    def test__get_previous_pid_v2__returns_none_because_there_is_none(self):
        pids_to_append_in_xml = [("xxx", "scielo-v2")]

        mock_article = MockArticle()

        result = spf_document._get_previous_pid_v2(
            pids_to_append_in_xml,
            mock_article,
            lambda x: None,
        )

        self.assertIsNone(result)
        self.assertEqual([("xxx", "scielo-v2")], pids_to_append_in_xml)


class TestSPFDocumentGetV3(unittest.TestCase):

    def test__get_pid_v3__returns_pid_in_xml(self):
        pids_to_append_in_xml = [("xxx", "scielo-v2")]

        pid_manager_v3 = {}
        in_xml = "S3456-09872009000554321"
        mock_article = MockArticle(pid_v3=in_xml)

        result = spf_document._get_pid_v3(
            pids_to_append_in_xml,
            mock_article,
            pid_manager_v3,
        )
        # retorna o mesmo valor que está no XML
        self.assertEqual(in_xml, result)
        # nao atualiza pids_to_append_in_xml
        self.assertEqual([("xxx", "scielo-v2")], pids_to_append_in_xml)

    def test__get_pid_v3__returns_got_from_pid_manager(self):
        pids_to_append_in_xml = [("xxx", "scielo-v2")]
        mock_article = MockArticle()
        pid_manager_v3 = "v3provided_by_pid_manager"

        result = spf_document._get_pid_v3(
            pids_to_append_in_xml,
            mock_article,
            pid_manager_v3,
        )

        self.assertEqual("v3provided_by_pid_manager", result)
        self.assertEqual(
            [("xxx", "scielo-v2"),
             ("v3provided_by_pid_manager", "scielo-v3")],
            pids_to_append_in_xml
        )

    def test__get_pid_v3__returns_got_new_pid_v3_from_pid_manager(self):
        pids_to_append_in_xml = [("xxx", "scielo-v2")]

        mock_article = MockArticle(pid_v3="v3_no_xml")
        pid_manager_v3 = "new_v3_provided_by_pid_manager"
        result = spf_document._get_pid_v3(
            pids_to_append_in_xml,
            mock_article,
            pid_manager_v3,
        )

        self.assertEqual("new_v3_provided_by_pid_manager", result)
        self.assertEqual([("xxx", "scielo-v2"),
                          ("new_v3_provided_by_pid_manager", "scielo-v3")],
                         pids_to_append_in_xml)


class TestSPFDocumentTransferPidV2ToPreviousPid(unittest.TestCase):

    def test__migrate_pid_v2_to_previous_pid(self):
        pids_to_append_in_xml = [("doc_pid_v2", "scielo-v2")]

        record = {"v2": "pid_manager_v2"}
        pid_v2 = "doc_pid_v2"
        prev_pid = None

        spf_document._migrate_pid_v2_to_previous_pid(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        self.assertEqual(
            [("doc_pid_v2", "scielo-v2"),
             ("pid_manager_v2", "previous-pid"),
             ],
            pids_to_append_in_xml)

    def test__migrate_pid_v2_to_previous_pid_does_not_migrate(self):
        pids_to_append_in_xml = [("pid_v2", "scielo-v2")]

        record = {"v2": "pid_v2"}
        pid_v2 = "pid_v2"
        prev_pid = None

        spf_document._migrate_pid_v2_to_previous_pid(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        # nao atualiza pids_to_append_in_xml
        self.assertEqual(
            [("pid_v2", "scielo-v2"),
             ],
            pids_to_append_in_xml)

    def test__migrate_pid_v2_to_previous_pid_does_not_migrate2(self):
        pids_to_append_in_xml = [("pid_v2", "scielo-v2")]

        # recuperado v2 diferente do v2 atual
        record = {"v2": "pid_v2"}
        pid_v2 = "pid_v2"

        # xml já tem previous pid
        prev_pid = "aop_pid"

        spf_document._migrate_pid_v2_to_previous_pid(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        # nao atualiza pids_to_append_in_xml
        self.assertEqual(
            [("pid_v2", "scielo-v2"),
             ],
            pids_to_append_in_xml)


class TestSPFDocumentGetPidsToAppendInXml(unittest.TestCase):

    def test__get_pids_to_append_in_xml__all_the_ids_were_generated_or_recovered(self):
        """
        Generate or recover v3 (v3 is returned by pid_manager)
        Build v2
        Recover previous_id from isis
        """
        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("saved_in_isis", "previous-pid"),
            ("generated_v3", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "saved": {
                "v2": "S3456-09872009000512345",
                "v3": "generated_v3",
                "aop": "saved_in_isis",
            }
        }
        expected_registered_v3 = "generated_v3"

        mock_article = MockArticle()
        mock_pid_manager = Mock()
        mock_pid_manager.manage = Mock()
        mock_pid_manager.manage.return_value = {
            "saved": {
                "v2": "S3456-09872009000512345",
                "v3": "generated_v3",
                "aop": "saved_in_isis",
            }
        }

        response = spf_document._get_pids_to_append_in_xml(
            pid_manager=mock_pid_manager,
            article=mock_article,
            issn_id="3456-0987",
            year_and_order="20095",
            file_path="/path/abc.xml",
            update_article_with_aop_status=mock_update_article_with_aop_status,
        )
        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

    def test__get_pids_to_append_in_xml__v3_generated_and_v2_built_and_no_previous_pid_exists(self):
        """
        Generate or recover v3 (v3 is returned by pid_manager)
        Build v2
        There is no previous_id in isis
        """
        def f(article):
            article.registered_aop_pid = None

        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("generated_v3", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "saved": {
                "v2": "S3456-09872009000512345",
                "v3": "generated_v3",
            }
        }
        expected_registered_v3 = "generated_v3"

        mock_article = MockArticle()
        mock_pid_manager = Mock()
        mock_pid_manager.manage = Mock()
        mock_pid_manager.manage.return_value = {
            "saved": {
                "v2": "S3456-09872009000512345",
                "v3": "generated_v3",
            }
        }

        response = spf_document._get_pids_to_append_in_xml(
            pid_manager=mock_pid_manager,
            article=mock_article,
            issn_id="3456-0987",
            year_and_order="20095",
            file_path="/path/abc.xml",
            update_article_with_aop_status=f,
        )
        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

    def test__get_pids_to_append_in_xml__pid_manager_returns_registered_v3_and_v2_different_from_built_v2(self):
        """
        pid_manager returns registered v3
        Build v2
        pid_manager returns a different v2 (pid de aop?)
        """
        def f(article):
            article.registered_aop_pid = None

        mock_article = MockArticle()
        mock_pid_manager = Mock()
        mock_pid_manager.manage = Mock()
        mock_pid_manager.manage.return_value = {
            "registered": {
                "v2": "pid_of_ex_ahead",
                "v3": "registered_v3",
            }
        }

        response = spf_document._get_pids_to_append_in_xml(
            pid_manager=mock_pid_manager,
            article=mock_article,
            issn_id="3456-0987",
            year_and_order="20095",
            file_path="/path/abc.xml",
            update_article_with_aop_status=f,
        )

        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("registered_v3", "scielo-v3"),
            ("pid_of_ex_ahead", "previous-pid"),
        ]

        expected_pid_manager_result = {
            "registered": {
                "v2": "pid_of_ex_ahead",
                "v3": "registered_v3",
            }
        }
        expected_registered_v3 = "registered_v3"

        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])


    def test__get_pids_to_append_in_xml__pid_manager_returns__(self):
        """
        pid_manager returns registered v3
        Build v2
        pid_manager returns a different v2 (pid de aop?)
        """
        def f(article):
            article.registered_aop_pid = None

        mock_article = MockArticle()
        mock_pid_manager = Mock()
        mock_pid_manager.manage = Mock()
        mock_pid_manager.manage.return_value = {
            "registered": {
                "v2": "v2_registered_at_pid_manager",
                "v3": "v3_registered_at_pid_manager",
                "aop": "aop_registered_at_pid_manager"
            }
        }

        response = spf_document._get_pids_to_append_in_xml(
            pid_manager=mock_pid_manager,
            article=mock_article,
            issn_id="3456-0987",
            year_and_order="20095",
            file_path="/path/abc.xml",
            update_article_with_aop_status=f,
        )

        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("v3_registered_at_pid_manager", "scielo-v3"),
            ("aop_registered_at_pid_manager", "previous-pid"),
        ]

        expected_pid_manager_result = {
            "registered": {
                "v2": "v2_registered_at_pid_manager",
                "v3": "v3_registered_at_pid_manager",
                "aop": "aop_registered_at_pid_manager"
            }
        }
        expected_registered_v3 = "v3_registered_at_pid_manager"

        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

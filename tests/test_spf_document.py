# coding:utf-8
import tempfile
import unittest
from unittest.mock import Mock, patch
import os

from io import StringIO

from lxml import etree
from copy import deepcopy
from prodtools.data import spf_document
from prodtools.data.article import Article


def load_xml(text):
    return etree.parse(StringIO(text), etree.XMLParser())


def mock_update_article_with_aop_status(article):
    article.registered_aop_pid = "saved_in_isis"


class MockContrib:

    def __init__(self, surname):
        self.surname = surname


class MockArticle:
    def __init__(self, pid_v3=None, pid_v2=None,
                 db_prev_pid=None, prev_pid=None,
                 order=None, number=None,
                 ):
        # este atributo não existe no Article real
        self._scielo_pid = pid_v2

        # estes atributos existem no Article real
        self.scielo_id = pid_v3
        self.registered_scielo_id = None
        self.registered_aop_pid = db_prev_pid
        self.previous_article_pid = prev_pid
        self.order = order or "12345"
        self.doi = ""
        self.number = number or "5"
        self.article_contrib_items = [MockContrib("Silva"), MockContrib("Souza"), ]
        self.titles = []
        self.real_pubdate = {"year": "2020"}
        self.volume = "31"
        self.suppl = "A"
        self.number_suppl = "B"
        self.volume_suppl = "C"
        self.elocation_id = "eloca"
        self.fpage = "fpage"
        self.lpage = "lpage"

    def get_scielo_pid(self, name):
        # simula o get_scielo_pid real
        if name == "v3":
            return self.scielo_id
        return self._scielo_pid


class TestSPFDocumentUpdateXmlFile(unittest.TestCase):

    def setUp(self):
        self.temporary_file = tempfile.mktemp()
        content = (
            """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">
                <article>
                    <article-meta>
                        <field>São Paulo - É, ê, È, ç</field>
                    </article-meta>
                </article>
            """
        )
        with open(self.temporary_file, "w") as fp:
            fp.write(content)

    def tearDown(self):
        try:
            os.unlink(self.temporary_file)
        except IOError:
            pass

    def test_update_xml_file_insert_article_id_elements(self):
        spf_document.update_xml_file(
            self.temporary_file,
            [("random-pid", "pid-v3"), ("random-pid-2", "pid-v2"), ]
        )
        with open(self.temporary_file) as fp:
            content = fp.read()
        self.assertIn(
            '<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            content,
        )
        self.assertIn(
            '<article-id specific-use="pid-v2" pub-id-type="publisher-id">random-pid-2</article-id>',
            content
        )

    def test_update_xml_file_should_not_modify_the_documents_doctype(self):
        spf_document.update_xml_file(
            self.temporary_file,
            [("random-pid", "pid-v3"), ("random-pid-2", "pid-v2"), ]
        )
        with open(self.temporary_file) as fp:
            content = fp.read()
        self.assertIn(
            """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">""",
            content
        )

    def test_update_xml_file_should_not_convert_character_to_entity(self):
        spf_document.update_xml_file(
            self.temporary_file,
            [("random-pid", "pid-v3"), ("random-pid-2", "pid-v2"), ]
        )
        with open(self.temporary_file) as fp:
            self.assertIn("São Paulo - É, ê, È, ç", fp.read())


class TestSPFDocumentWriteFile(unittest.TestCase):

    def setUp(self):
        self.tree = load_xml(
            """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">
                <article>
                    <article-meta>
                        <field>São Paulo - É, ê, È, ç</field>
                    </article-meta>
                </article>
            """
        )

    def test_add_pids_to_etree_should_return_none_if_etree_is_not_valid(self):
        self.assertIsNone(spf_document.update_article_id_in_xml(None, []))

    def test_add_pids_to_etree_should_not_update_if_pid_list_is_empty(self):
        tree = etree.fromstring("<article><article-meta></article-meta></article>")
        self.assertIsNone(spf_document.update_article_id_in_xml(tree, []))

    def test_add_pids_to_etree_insert_article_id_elements(self):
        tree = etree.fromstring(
            """<article>
                <article-meta></article-meta>
            </article>"""
        )
        _tree = spf_document.update_article_id_in_xml(
            tree, [("random-pid", "pid-v3"), ("random-pid-2", "pid-v2"), ]
        )
        self.assertIn(
            b'<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            etree.tostring(_tree),
        )
        self.assertIn(
            b'<article-id specific-use="pid-v2" pub-id-type="publisher-id">random-pid-2</article-id>',
            etree.tostring(_tree),
        )

    def test_update_article_id_in_xml__delete_article_id(self):
        tree = etree.fromstring(
            """<article>
                <article-meta>
            <article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>
                </article-meta>
            </article>"""
        )
        _tree = spf_document.update_article_id_in_xml(
            tree, [(None, "pid-v3"),]
        )
        self.assertNotIn(
            b'<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            etree.tostring(_tree),
        )

    def test_add_pids_to_etree_should_etree_with_pid_v3(self):
        tree = etree.fromstring(
            """<article>
                <article-meta></article-meta>
            </article>"""
        )
        _tree = spf_document.update_article_id_in_xml(
            tree, [("random-pid", "pid-v3",)]
        )
        self.assertIn(
            b'<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            etree.tostring(_tree),
        )

    def test_add_pids_to_etree_should_not_modify_the_documents_doctype(self):
        _tree = spf_document.update_article_id_in_xml(
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

    def test__get_pids_to_append_in_xml__new_document_and_not_ex_aop(self):
        """
        Test registration of new document, not aop
        - v3 = generated
        - v2 = built using issn, year, issue_order, order
        - no previous-pid
        """
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

        mock_article = MockArticle(order="12345")

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "saved": {
                "v2": "S3456-09872009000512345",
                "v3": "generated_v3",
            }
        }

        mock_update_article_with_aop_status = Mock(return_value=None)

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

    def test__get_pids_to_append_in_xml__new_document_and_is_aop(self):
        """
        Test registration of new document which is aop
        - v3 = generated
        - v2 = built using issn, year, issue_order, order
        - no previous-pid
        """
        expected_pids_to_append_in_xml = [
            ("S3456-09872009005099345", "scielo-v2"),
            ("generated_v3", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "saved": {
                "v2": "S3456-09872009005099345",
                "v3": "generated_v3",
            }
        }
        expected_registered_v3 = "generated_v3"

        mock_update_article_with_aop_status = Mock(return_value=None)

        mock_article = MockArticle(order="99345")

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "saved": {
                "v2": "S3456-09872009005099345",
                "v3": "generated_v3",
            }
        }

        response = spf_document._get_pids_to_append_in_xml(
            pid_manager=mock_pid_manager,
            article=mock_article,
            issn_id="3456-0987",
            year_and_order="200950",
            file_path="/path/abc.xml",
            update_article_with_aop_status=mock_update_article_with_aop_status,
        )
        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

    def test__get_pids_to_append_in_xml__new_document_but_has_aop_version(self):
        """
        Test new version of document which current version is aop
        - v3 = recover from pid_manager
        - v2 = built using issn, year, issue_order, order
        - previous_pid = recover from isis
        """
        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("saved_in_isis", "previous-pid"),
            ("v3_recovered_from_pid_manager", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "v3_recovered_from_pid_manager",
                "aop": "saved_in_isis",
            }
        }
        expected_registered_v3 = "v3_recovered_from_pid_manager"

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "v3_recovered_from_pid_manager",
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

    def test__get_pids_to_append_in_xml__update_document_which_has_no_previous_id(self):
        """
        Test update document which has no previous_pid
        - v3 = recover from pid_manager
        - v2 = built using issn, year, issue_order, order /
               but confirmed by pid_manager
        - previous_pid = none
        """
        def f(article):
            article.registered_aop_pid = None

        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("recovered_v3", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "recovered_v3",
            }
        }
        expected_registered_v3 = "recovered_v3"

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "recovered_v3",
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

    def test__get_pids_to_append_in_xml__update_document_which_has_previous_id(self):
        """
        Test update document which has previous_pid
        - v3 = recover from pid_manager
        - v2 = built using issn, year, issue_order, order /
               it is also registered in pid_manager as v2
        - previous_pid = recover from isis and
                         it is also registered in pid_manager as aop
        """
        def f(article):
            article.registered_aop_pid = "S3456-09872009005092345"

        expected_pids_to_append_in_xml = [
            ("S3456-09872009000512345", "scielo-v2"),
            ("S3456-09872009005092345", "previous-pid"),
            ("recovered_v3", "scielo-v3"),
        ]
        expected_pid_manager_result = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "recovered_v3",
                "aop": "S3456-09872009005092345",
            }
        }
        expected_registered_v3 = "recovered_v3"

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "recovered_v3",
                "aop": "S3456-09872009005092345",
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
        Test new document, previous-pid recovered from pid_manager, not from isis
        - v3 = recover from pid_manager
        - v2 = built using issn, year, issue_order, order /
               but found other v2 registered in pid_manager (version aop)
        - previous_pid = none (not registered in isis)
        """
        def f(article):
            article.registered_aop_pid = None

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "registered_v3",
                "aop": "S3456-09872009005099345",
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
            ("S3456-09872009005099345", "previous-pid"),
        ]

        expected_pid_manager_result = {
            "registered": {
                "v2": "S3456-09872009000512345",
                "v3": "registered_v3",
                "aop": "S3456-09872009005099345",
            }
        }
        expected_registered_v3 = "registered_v3"

        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

    def test__get_pids_to_append_in_xml__pid_manager__new_metadata_but_v2_belongs_to_another_document(self):
        """
        Test register document with conflicts:
            - METADATA are NOT REGISTERED (new document)
            - v2 is REGISTERED (another document)

        then keep the conflicting v2, because:
        a) v3 and the other metadata will be used to desambiguation purpose
        b) probably the other document v2 was also changed to other ID

        - create new record
        - v3 = generates new record, with new v3
        - v2 = built using issn, year, issue_order, order /
               use the conflicting v2 as v2 for the new record
        """
        def f(article):
            article.registered_aop_pid = None

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
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

        self.assertEqual(
            expected_pids_to_append_in_xml, response['pids_to_append_in_xml'])
        self.assertEqual(
            expected_pid_manager_result, response['pid_manager_result'])
        self.assertEqual(
            expected_registered_v3, response['registered_v3'])

    def test__get_pids_to_append_in_xml__pid_manager__v2_changed(self):
        """
        Test register document with conflicts:
            - METADATA are REGISTERED (document is registered)
            - registered v2 does not match with document v2

        - update same record
        - v3 = recover v3
        - v2 = built using issn, year, issue_order, order /
               it does not match with registered v2 and it is not aop version /
               v2 was changed / accept the document v2 as update /
               replace v2
        """
        def f(article):
            article.registered_aop_pid = None

        mock_article = MockArticle()

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs = Mock()
        # saved = new record, recently created
        # registered = query result
        mock_pid_manager.manage_docs.return_value = {
            "registered": {
                "v2": "S3456-09872009000512345",
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
        ]

        expected_pid_manager_result = {
            "registered": {
                "v2": "S3456-09872009000512345",
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


class TestSPFDocumentAddArticleIdToReceivedDocuments(unittest.TestCase):

    def setUp(self):
        self.files = ["file" + str(i) + ".xml" for i in range(1, 6)]
        for f in self.files:
            with open(f, "wb") as fp:
                fp.write(b"<article><article-meta></article-meta></article>")
        self.received = {
            "file1": MockArticle(None, None, order="00001"),
            "file2": MockArticle(None, None, order="00002"),
            "file3": MockArticle(None, None, order="00003"),
            "file4": MockArticle(None, None, order="00004"),
        }
        self.file_paths = {
            name: fname
            for name, fname in zip(self.received.keys(), self.files)
        }
        self.issn_id = "9876-3456"
        self.year_and_order = "20173"

    def tearDown(self):
        for f in self.files:
            try:
                os.unlink(f)
            except IOError:
                pass

    def test__add_article_id_to_received_documents__inserted_ids_in_xml(self):
        registered = {}
        results = {}

        # pid_manager é um módulo da biblioteca scielo_v3_manager
        # which has to manage the data conflicts, v3 generation or recover
        # and other related questions
        mock_pid_manager = Mock()
        mock_pid_manager.manage_docs.side_effect = [
            {"saved" :{
                "v3": "generated_v3_1",
                "v2": "S9876-34562017000300001",
            }},
            {"registered": {
                "v3": "registered_v3",
                "v2": "S9876-34562017000300002",
            }},
            {"saved": {
                "v3": "generated_v3_3",
                "v2": "S9876-34562017000300003",
                "aop": "recovered_from_isis",
            }},
            {"registered": {
                "v3": "registered_v3_4",
                "v2": "S9876-34562017000300004",
                "aop": "recovered_from_isis_4",
            }}
        ]

        mock_update_article_with_aop_status = Mock(
            side_effect=[
                None, None, "recovered_from_isis", "recovered_from_isis_4"
            ]
        )

        spf_document.generates = Mock(
            side_effect=[
                "generated_v3_1",
                "generated_v3_3",
            ]
        )
        spf_document._add_article_id_to_received_documents(
            pid_manager=mock_pid_manager,
            issn_id=self.issn_id,
            year_and_order=self.year_and_order,
            received_docs=self.received,
            file_paths=self.file_paths,
            update_article_with_aop_status=mock_update_article_with_aop_status,
            registered_v3_items=registered,
            results=results,
        )
        expected = [
            {
                "scielo-v3": "generated_v3_1",
                "scielo-v2": "S9876-34562017000300001",
            },
            {
                "scielo-v3": "registered_v3",
                "scielo-v2": "S9876-34562017000300002",
            },
            {
                "scielo-v3": "generated_v3_3",
                "scielo-v2": "S9876-34562017000300003",
                "previous-pid": "recovered_from_isis",
            },
            {
                "scielo-v3": "registered_v3_4",
                "scielo-v2": "S9876-34562017000300004",
                "previous-pid": "recovered_from_isis_4",
            },
        ]
        for index, recv in enumerate(self.received.items()):
            name, item = recv
            with self.subTest(name):
                with open(self.file_paths[name], "r") as fp:
                    c = fp.read()
                    print(c)
                xml = etree.fromstring(c)
                self.assertEqual(
                    expected[index].get('scielo-v3'),
                    xml.findtext(".//article-id[@specific-use='scielo-v3']")
                )
                self.assertEqual(
                    expected[index].get('scielo-v2'),
                    xml.findtext(".//article-id[@specific-use='scielo-v2']")
                )
                self.assertEqual(
                    expected[index].get('previous-pid'),
                    xml.findtext(".//article-id[@specific-use='previous-pid']")
                )
        self.assertDictEqual(
            {"file1":
                {"saved" :{
                    "v3": "generated_v3_1",
                    "v2": "S9876-34562017000300001",
                }},
            "file2": {"registered": {
                    "v3": "registered_v3",
                    "v2": "S9876-34562017000300002",
                }},
            "file3": {"saved": {
                    "v3": "generated_v3_3",
                    "v2": "S9876-34562017000300003",
                    "aop": "recovered_from_isis",
                }},
            "file4": {"registered": {
                    "v3": "registered_v3_4",
                    "v2": "S9876-34562017000300004",
                    "aop": "recovered_from_isis_4",
                }}
            },
            results
        )
        self.assertDictEqual({
                "file1": "generated_v3_1",
                "file2": "registered_v3",
                "file3": "generated_v3_3",
                "file4": "registered_v3_4",
            },
            registered
        )


class TestSPFDocumentupdatePidValuesWithValuesRegisteredInPidManager(unittest.TestCase):

    def test__update_pid_values_with_values_registered_in_pid_manager__updates_v2_and_previous_pid(self):
        pids_to_append_in_xml = [("doc_pid_v2", "scielo-v2")]

        record = {"v2": "pid_manager_v2", "aop": "pid_manager_aop"}
        pid_v2 = "doc_pid_v2"
        prev_pid = None

        spf_document._update_pid_values_with_values_registered_in_pid_manager(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        self.assertEqual(
            [("doc_pid_v2", "scielo-v2"),
             ("pid_manager_v2", "scielo-v2"),
             ("pid_manager_aop", "previous-pid"),
             ],
            pids_to_append_in_xml)

    def test__update_pid_values_with_values_registered_in_pid_manager__updates_previous_pid_only(self):
        pids_to_append_in_xml = [("doc_pid_v2", "scielo-v2")]

        record = {"v2": "doc_pid_v2", "aop": "pid_manager_aop"}
        pid_v2 = "doc_pid_v2"
        prev_pid = None

        spf_document._update_pid_values_with_values_registered_in_pid_manager(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        self.assertEqual(
            [("doc_pid_v2", "scielo-v2"), ("pid_manager_aop", "previous-pid")],
            pids_to_append_in_xml
        )

    def test__update_pid_values_with_values_registered_in_pid_manager__delete_previous_pid(self):
        pids_to_append_in_xml = [("pid_v2", "scielo-v2")]

        record = {"v2": "pid_v2"}
        pid_v2 = "pid_v2"
        prev_pid = "aop_pid"

        spf_document._update_pid_values_with_values_registered_in_pid_manager(
            pids_to_append_in_xml,
            record, pid_v2, prev_pid,
        )
        self.assertEqual(
            [("pid_v2", "scielo-v2"), (None, "previous-pid")],
            pids_to_append_in_xml
        )


@patch("prodtools.data.spf_document.generates")
@patch("prodtools.data.spf_document.Manager")
class TestSPFDocumentManage(unittest.TestCase):

    def setUp(self):
        content = (
            """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">
                <article xml:lang="pt">
                    <front>
                    <article-meta>
                        <field>São Paulo - É, ê, È, ç</field>
                        <article-id pub-id-type="doi">10.1590/abcdefdoi</article-id>
                        <title-group><article-title>Este é o título do artigo em português</article-title></title-group>
                        <pub-date date-type="pub">
                            <year>2008</year>
                        </pub-date>
                        <volume>3</volume>
                        <issue>2 suppl A</issue>
                        <fpage>12</fpage>
                        <lpage>34</lpage>
                        <contrib-group>
                            <contrib><surname>Kotlin</surname></contrib>
                            <contrib><surname>Silva</surname></contrib>
                            <contrib><surname>Sousa</surname></contrib>
                            <contrib><surname>Linklus</surname></contrib>
                        </contrib-group>
                    </article-meta>
                    </front>
                </article>
            """
        )
        self.file_path = "/path/article.xml"
        self.article = Article(etree.fromstring(content), "article.xml")

    def test_manage(self, mock_pid_manager, mock_v3_gen):
        pid_v2 = "S9876-34562017000300002"
        pid_v3 = "DtRHRnPspwkW46DsyczM6wH"
        prev_pid = "S9876-34562017005000002"
        year_and_order = "20082"

        result = spf_document._manage_pids(
            mock_pid_manager,
            pid_v2, pid_v3, prev_pid,
            year_and_order,
            self.file_path,
            self.article,
        )
        mock_pid_manager.manage_docs.assert_called_with(
            generate_v3=mock_v3_gen,
            v2=pid_v2,
            v3=pid_v3,
            aop=prev_pid,
            filename="article.xml",
            doi="10.1590/abcdefdoi",
            status="",
            pub_year="2008",
            issue_order="2",
            volume="3",
            number="2",
            suppl="a",
            elocation=None,
            fpage="12",
            lpage="34",
            first_author_surname="Kotlin",
            last_author_surname="Linklus",
            article_title="Este é o título do artigo em português",
            other_pids="",
        )

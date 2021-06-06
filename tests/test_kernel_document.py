# coding:utf-8
import tempfile
import unittest
from unittest.mock import Mock, patch
import os

from io import StringIO

from lxml import etree
from copy import deepcopy
from prodtools.data import kernel_document


class MockArticle:
    def __init__(self, pid_v3, pid_v2, db_prev_pid=None, prev_pid=None):
        # este atributo não existe no Article real
        self._scielo_pid = pid_v2

        # estes atributos existem no Article real
        self.scielo_id = pid_v3
        self.registered_scielo_id = None
        self.registered_aop_pid = db_prev_pid
        self.previous_article_pid = prev_pid
        self.order = "12345"

    def get_scielo_pid(self, name):
        # simula o get_scielo_pid real
        if name == "v3":
            return self.scielo_id
        return self._scielo_pid


class TestKernelDocumentAddArticleIdToReceivedDocuments(unittest.TestCase):
    def setUp(self):
        self.files = ["file" + str(i) + ".xml" for i in range(1, 6)]
        for f in self.files:
            with open(f, "wb") as fp:
                fp.write(b"<article><article-meta></article-meta></article>")

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

    def test_add_article_id_to_received_documents(self):
        registered = {
            "file1": MockArticle(None, None),
            "file2": MockArticle("xyzwx", None),
            "file3": MockArticle(None, "09873"),
            "file4": MockArticle("Akouuad", "83847"),
        }
        received = {
            "file1": MockArticle(None, None),
            "file2": MockArticle(None, None),
            "file3": MockArticle(None, None),
            "file4": MockArticle(None, None),
        }
        file_paths = {
            name: fname
            for name, fname in zip(registered.keys(), self.files)
        }
        issn_id = "9876-3456"
        year_and_order = "20173"

        mock_pid_manager = Mock()
        mock_pid_manager.get_most_recent_pid_v3.return_value = None

        kernel_document.scielo_id_gen.generate_scielo_pid = Mock(return_value="xxxxxx")
        kernel_document.add_article_id_to_received_documents(
            mock_pid_manager, issn_id, year_and_order, received,
            registered, file_paths, lambda x:x
        )

        for name, item in received.items():
            registered_doc = registered.get(name)

            expected_scielo_id = "xxxxxx"
            with self.subTest(name):
                # é esperado que item.registered_scielo_id seja atualizado com
                # xxxxxx, mesmo que já tinha outro valor
                self.assertEqual(item.registered_scielo_id, expected_scielo_id)
                with open(file_paths[name], "r") as fp:
                    content = fp.read()
                    self.assertIn("article-id", content)
                    self.assertIn("S9876-34562017000312345", content)
                    self.assertIn('specific-use="scielo-v3"', content)
                    self.assertIn('specific-use="scielo-v2"', content)
                    self.assertIn(expected_scielo_id, content)

    def test_pid_manager_should_use_aop_pid_to_search_pid_v3_from_database(self,):
        def _update_article_with_aop_pid(article: MockArticle):
            article.registered_aop_pid = "AOPPID"

        mock_pid_manager = Mock()
        mock_pid_manager.get_most_recent_pid_v3 = self._return_scielo_pid_v3_if_aop_pid_match

        kernel_document.add_article_id_to_received_documents(
            pid_manager=mock_pid_manager,
            issn_id="9876-3456",
            year_and_order="20173",
            received_docs={"file1": MockArticle(None, None)},
            documents_in_isis={},
            file_paths={},
            update_article_with_aop_status=_update_article_with_aop_pid,
        )

        mock_pid_manager.pids_already_registered.assert_called_with(
            "S9876-34562017000312345",
            "pid-v3-registrado-anteriormente-para-documento-aop",
        )

    def test_pid_manager_should_try_to_register_pids_even_it_already_exists_in_xml(
        self,
    ):

        mock_pid_manager = Mock()

        kernel_document.add_article_id_to_received_documents(
            pid_manager=mock_pid_manager,
            issn_id="9876-3456",
            year_and_order="20173",
            received_docs={"file1": MockArticle("brzWFrVFdpYMXdpvq7dDJBQ", None)},
            documents_in_isis={},
            file_paths={},
            update_article_with_aop_status=lambda _: _,
        )

        self.assertTrue(mock_pid_manager.pids_already_registered.called)

    def test_add_pids_to_etree_should_return_none_if_etree_is_not_valid(self):
        self.assertIsNone(kernel_document.add_article_id_to_etree(None, []))

    def test_add_pids_to_etree_should_not_update_if_pid_list_is_empty(self):
        tree = etree.fromstring("<article><article-meta></article-meta></article>")
        self.assertIsNone(kernel_document.add_article_id_to_etree(tree, []))

    def test_add_pids_to_etree_should_etree_with_pid_v3(self):
        tree = etree.fromstring(
            """<article>
                <article-meta></article-meta>
            </article>"""
        )
        _tree = kernel_document.add_article_id_to_etree(
            tree, [("random-pid", "pid-v3",)]
        )
        self.assertIn(
            b'<article-id specific-use="pid-v3" pub-id-type="publisher-id">random-pid</article-id>',
            etree.tostring(_tree),
        )

    def test_add_pids_to_etree_should_not_modify_the_documents_doctype(self):
        _tree = kernel_document.add_article_id_to_etree(
            self.tree, [("random-pid", "pid-v3",)]
        )
        self.assertIn(
            b"""<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">""",
            etree.tostring(_tree),
        )

    def test_write_etree_to_file_should_not_update_file_if_etree_is_none(self):
        temporary_file = tempfile.mktemp()
        kernel_document.write_etree_to_file(None, path=temporary_file)
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
        kernel_document.write_etree_to_file(tree, path=temporary_file)

        with open(temporary_file, "r") as f:
            self.assertIn("São Paulo - É, ê, È, ç", f.read())

    def test_write_etree_to_file_should_not_change_the_document_doctype(self):
        temporary_file = tempfile.mktemp()
        kernel_document.write_etree_to_file(self.tree, path=temporary_file)

        with open(temporary_file, "r") as f:
            self.assertIn(
                """<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD v1.1 20151215//EN" "https://jats.nlm.nih.gov/publishing/1.1/JATS-journalpublishing1.dtd">""",
                f.read(),
            )

    @patch("prodtools.data.kernel_document.write_etree_to_file")
    def test_should_call_the_write_etree_to_file_when_the_pid_list_isnt_empty(self, mk):
        kernel_document.add_article_id_to_received_documents(
            pid_manager=Mock(),
            issn_id="9876-3456",
            year_and_order="20173",
            received_docs={"file1": MockArticle("pid-v3", None)},
            documents_in_isis={},
            file_paths={"file1": "file1.xml"},
            update_article_with_aop_status=lambda _: _,
        )

        self.assertTrue(mk.called)


class TestKernelDocument(unittest.TestCase):
    """docstring for TestKernelDocument"""

    def test_get_scielo_pid_v2(self):
        result = kernel_document.get_scielo_pid_v2(
            issn_id="3456-0987",
            year_and_order="20095",
            order_in_issue="54321")
        self.assertEqual("S3456-09872009000554321", result)

    @unittest.skip("kernel_document.get_scielo_pid_v3 foi removida no PR 3171")
    @patch("prodtools.data.kernel_document.scielo_id_gen.generate_scielo_pid")
    def test_get_scielo_pid_v3_returns_a_new_scielo_id(self, mocked_generate_scielo_pid):
        registered = Mock()
        registered.scielo_id = None
        mocked_generate_scielo_pid.return_value = "GENERATED"
        result = kernel_document.get_scielo_pid_v3(registered)
        self.assertEqual("GENERATED", result)

    @unittest.skip("kernel_document.get_scielo_pid_v3 foi removida no PR 3171")
    @patch("prodtools.data.kernel_document.scielo_id_gen.generate_scielo_pid")
    def test_get_scielo_pid_v3_returns_previously_registered_scielo_id(self, mocked_generate_scielo_pid):
        registered = Mock()
        registered.scielo_id = "REGISTERED"
        mocked_generate_scielo_pid.return_value = "GENERATED"
        result = kernel_document.get_scielo_pid_v3(registered)
        self.assertEqual("REGISTERED", result)

    @unittest.skip("kernel_document.add_article_id foi removida no PR 3171")
    def test_add_article_id_create_article_id_which_specific_use_is_scielo_v3(self):
        article_meta = etree.Element("article-meta")
        id_value = "01"
        specific_use = "scielo-v3"
        kernel_document.add_article_id(article_meta, id_value, specific_use)
        article_id = article_meta.find("article-id")
        self.assertEqual(article_id.text, id_value)
        self.assertEqual(article_id.get("specific-use"), specific_use)

    @unittest.skip("kernel_document.add_article_id foi removida no PR 3171")
    def test_add_article_id_create_article_id_which_specific_use_is_scielo_v2(self):
        article_meta = etree.Element("article-meta")
        id_value = "01"
        specific_use = "scielo-v2"
        kernel_document.add_article_id(article_meta, id_value, specific_use)
        article_id = article_meta.find("article-id")
        self.assertEqual(article_id.text, id_value)
        self.assertEqual(article_id.get("specific-use"), specific_use)

# coding:utf-8
import tempfile
import unittest
from unittest.mock import Mock, patch
import os

from io import StringIO

from lxml import etree
from copy import deepcopy
from prodtools.data import spf_document


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
    """docstring for TestSPFDocument"""

    def test_build_scielo_pid_v2(self):
        result = spf_document.build_scielo_pid_v2(
            issn_id="3456-0987",
            year_and_order="20095",
            order_in_issue="54321")
        self.assertEqual("S3456-09872009000554321", result)


class TestSPFDocumentGetPidV2(unittest.TestCase):
    """docstring for TestSPFDocument"""

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


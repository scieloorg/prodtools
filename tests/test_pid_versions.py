import os
import tempfile
import unittest
import sqlalchemy
from unittest.mock import Mock, call, patch

from prodtools.db.pid_versions import PIDVersionsManager, PidVersion


class TestPIDVersionsManager(unittest.TestCase):
    def setUp(self):
        self.temporary_db = tempfile.mkstemp(suffix=".db")[-1]
        self.manager = PIDVersionsManager("sqlite:///" + self.temporary_db)
        self.manager.register("pid-2", "pid-3")

    def tearDown(self):
        os.remove(self.temporary_db)

    def test_should_raise_exception_when_could_not_open_database_file(self):
        with self.assertRaises(sqlalchemy.exc.ArgumentError):
            fake_db_file = os.path.join(tempfile.gettempdir(), "fake-folder", "fake-file.db")
            PIDVersionsManager(fake_db_file)
            os.remove(fake_db_file)

    def test_should_insert_a_pair_of_pids(self):
        self.assertTrue(self.manager.register("random-v2", "random-v3"))

    def test_should_not_insert_duplicated_pids(self):
        self.assertFalse(self.manager.register("pid-2", "pid-3"))

    def test_should_retrieve_scielo_pid_v3_using_pid_v2(self):
        self.assertEqual(self.manager.get_pid_v3("pid-2"), "pid-3")

    def test_should_return_none_if_pid_v2_is_not_registered_yet(self):
        self.assertEqual(self.manager.get_pid_v3("does-not-exists"), None)

    def test_check_if_pids_already_registered_in_database(self):
        self.assertTrue(self.manager.pids_already_registered("pid-2", "pid-3"))

    def test_remove_records(self):
        self.manager.session.delete = Mock()
        self.manager._remove_records(["a", "b"], "a")

        self.assertListEqual(
            self.manager.session.delete.call_args_list,
            [call("b")]
        )

    @patch("prodtools.db.pid_versions.PidVersion")
    def test_add_records(self, MockPidVersion):
        self.manager.session.add = Mock()
        self.manager._add_records([("a", "b"), ("x", "y"), ("", "z")])

        calls = [
            call(MockPidVersion(v2="a", v3="b")),
            call(MockPidVersion(v2="x", v3="y")),
        ]
        self.assertEqual(
            calls,
            self.manager.session.add.call_args_list,
        )

    # def test_pid_manager_should_use_aop_pid_to_search_pid_v3_from_database(self,):
    #     def _update_article_with_aop_pid(article: MockArticle):
    #         article.registered_aop_pid = "AOPPID"

    #     mock_pid_manager = Mock()
    #     mock_pid_manager.get_pid_v3 = self._return_scielo_pid_v3_if_aop_pid_match

    #     kernel_document.add_article_id_to_received_documents(
    #         pid_manager=mock_pid_manager,
    #         issn_id="9876-3456",
    #         year_and_order="20173",
    #         received_docs={"file1": MockArticle(None, None)},
    #         documents_in_isis={},
    #         file_paths={},
    #         update_article_with_aop_status=_update_article_with_aop_pid,
    #     )

    #     mock_pid_manager.register.assert_called_with(
    #         "S9876-34562017000312345",
    #         "pid-v3-registrado-anteriormente-para-documento-aop",
    #     )

    # def test_pid_manager_should_try_to_register_pids_even_it_already_exists_in_xml(
    #     self,
    # ):

    #     mock_pid_manager = Mock()

    #     kernel_document.add_article_id_to_received_documents(
    #         pid_manager=mock_pid_manager,
    #         issn_id="9876-3456",
    #         year_and_order="20173",
    #         received_docs={"file1": MockArticle("brzWFrVFdpYMXdpvq7dDJBQ", None)},
    #         documents_in_isis={},
    #         file_paths={},
    #         update_article_with_aop_status=lambda _: _,
    #     )

    #     self.assertTrue(mock_pid_manager.register.called)

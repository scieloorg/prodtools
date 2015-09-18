# coding=utf-8

import sys
import os
from datetime import datetime

from __init__ import _
import attributes
import article_reports
import article_utils
import xpchecker
import html_reports
import utils
import fs_utils


log_items = []


class PkgManager(object):

    def __init__(self, pkg_articles):
        self.pkg_articles = pkg_articles
        self.issue_models = None
        self.issue_files = None
        self._registered_issue_data_validations = None
        self._blocking_errors = None
        self.pkg_conversion_results = None
        self.consistence_blocking_errors = None
        self._xml_name_sorted_by_order = None
        self._indexed_by_order = None
        self.changed_orders = None
        self.reftype_and_sources = None
        self.actions = None
        self.is_db_generation = False
        self._compiled_pkg_metadata = None
        self.changed_orders_validations = None

        self.expected_equal_values = ['journal-title', 'journal id NLM', 'e-ISSN', 'print ISSN', 'publisher name', 'issue label', 'issue pub date', ]
        self.expected_unique_value = ['order', 'doi', 'elocation id', ]

        self.error_level_for_unique = {'order': 'FATAL ERROR', 'doi': 'FATAL ERROR', 'elocation id': 'FATAL ERROR', 'fpage-lpage-seq': 'FATAL ERROR'}
        self.required_journal_data = ['journal-title', 'journal ISSN', 'publisher name', 'issue label', 'issue pub date', ]

        if not self.is_db_generation:
            self.error_level_for_unique['order'] = 'WARNING'

        if self.is_processed_in_batches:
            self.error_level_for_unique['fpage-lpage-seq'] = 'WARNING'
        else:
            self.expected_unique_value += ['fpage-lpage-seq']

    def xml_name_sorted_by_order(self):
        if self._xml_name_sorted_by_order is None:
            self._xml_name_sorted_by_order = self.sort_xml_name_by_order()
        return self._xml_name_sorted_by_order

    def sort_xml_name_by_order(self):
        order_and_xml_name_items = {}
        for xml_name, doc in self.pkg_articles.items():
            _order = str(doc.order)
            if not _order in order_and_xml_name_items.keys():
                order_and_xml_name_items[_order] = []
            order_and_xml_name_items[_order].append(xml_name)

        sorted_items = []
        for order in sorted(order_and_xml_name_items.keys()):
            for item in order_and_xml_name_items[order]:
                sorted_items.append(item)
        return sorted_items

    @property
    def indexed_by_order(self):
        if self._indexed_by_order is None:
            self._indexed_by_order = self.index_by_order()
        return self._indexed_by_order

    def index_by_order(self):
        indexed = {}
        for xml_name, article in self.pkg_articles.items():
            _order = str(article.order)
            if not _order in indexed.keys():
                indexed[_order] = []
            indexed[_order].append(article)
        return indexed

    @property
    def blocking_errors(self):
        if self._blocking_errors is None:
            if self.registered_issue_data_validations is not None:
                self._blocking_errors = self.registered_issue_data_validations.fatal_errors
        return self._blocking_errors + self.consistence_blocking_errors

    @property
    def registered_issue_data_validations(self):
        if self._registered_issue_data_validations is None:
            self._registered_issue_data_validations = PackageValidationsResults()
            for xml_name, article in self.pkg_articles.items():
                self.pkg_articles[xml_name].section_code, issue_validations_msg = self.validate_article_issue_data(article)
                self._registered_issue_data_validations.add(xml_name, ValidationsResults(issue_validations_msg))
        return self._registered_issue_data_validations

    def validate_article_issue_data(self, article):
        results = []
        section_code = None
        if self.issue_models is not None:
            if article.tree is not None:
                validations = []
                validations.append((_('journal title'), article.journal_title, self.issue_models.issue.journal_title))
                validations.append((_('journal id NLM'), article.journal_id_nlm_ta, self.issue_models.issue.journal_id_nlm_ta))

                a_issn = article.journal_issns.get('epub') if article.journal_issns is not None else None
                if a_issn is not None:
                    i_issn = self.issue_models.issue.journal_issns.get('epub') if self.issue_models.issue.journal_issns is not None else None
                    validations.append((_('journal e-ISSN'), a_issn, i_issn))

                a_issn = article.journal_issns.get('ppub') if article.journal_issns is not None else None
                if a_issn is not None:
                    i_issn = self.issue_models.issue.journal_issns.get('ppub') if self.issue_models.issue.journal_issns is not None else None
                    validations.append((_('journal print ISSN'), a_issn, i_issn))

                validations.append((_('issue label'), article.issue_label, self.issue_models.issue.issue_label))
                a_year = article.issue_pub_dateiso[0:4] if article.issue_pub_dateiso is not None else ''
                i_year = self.issue_models.issue.dateiso[0:4] if self.issue_models.issue.dateiso is not None else ''
                if self.issue_models.issue.dateiso is not None:
                    _status = 'FATAL ERROR'
                    if self.issue_models.issue.dateiso.endswith('0000'):
                        _status = 'WARNING'
                validations.append((_('issue pub-date'), a_year, i_year))

                # check issue data
                for label, article_data, issue_data in validations:
                    if article_data is None:
                        article_data = 'None'
                    elif isinstance(article_data, list):
                        article_data = ' | '.join(article_data)
                    if issue_data is None:
                        issue_data = 'None'
                    elif isinstance(issue_data, list):
                        issue_data = ' | '.join(issue_data)
                    if not article_data == issue_data:
                        _msg = _('data mismatched. In article: "') + article_data + _('" and in issue: "') + issue_data + '"'
                        if issue_data == 'None':
                            status = 'ERROR'
                        else:
                            if label == 'issue pub-date':
                                status = _status
                            else:
                                status = 'FATAL ERROR'
                        results.append((label, status, _msg))

                validations = []
                validations.append(('publisher', article.publisher_name, self.issue_models.issue.publisher_name))
                for label, article_data, issue_data in validations:
                    if article_data is None:
                        article_data = 'None'
                    elif isinstance(article_data, list):
                        article_data = ' | '.join(article_data)
                    if issue_data is None:
                        issue_data = 'None'
                    elif isinstance(issue_data, list):
                        issue_data = ' | '.join(issue_data)
                    if utils.how_similar(article_data, issue_data) < 0.8:
                        _msg = _('data mismatched. In article: "') + article_data + _('" and in issue: "') + issue_data + '"'
                        results.append((label, 'ERROR', _msg))

                # license
                if self.issue_models.issue.license is None:
                    results.append(('license', 'ERROR', _('Unable to identify issue license')))
                elif article.license_url is not None:
                    if not '/' + self.issue_models.issue.license.lower() in article.license_url.lower():
                        results.append(('license', 'ERROR', _('data mismatched. In article: "') + article.license_url + _('" and in issue: "') + self.issue_models.issue.license + '"'))
                    else:
                        results.append(('license', 'INFO', _('In article: "') + article.license_url + _('" and in issue: "') + self.issue_models.issue.license + '"'))

                # section
                section_code, matched_rate, fixed_sectitle = self.issue_models.most_similar_section_code(article.toc_section)
                if matched_rate != 1:
                    if not article.is_ahead:
                        registered_sections = _('Registered sections') + ':\n' + '; '.join(self.issue_models.section_titles)
                        if section_code is None:
                            results.append(('section', 'ERROR', article.toc_section + _(' is not a registered section.') + ' ' + registered_sections))
                        else:
                            results.append(('section', 'WARNING', _('section replaced: "') + fixed_sectitle + '" (' + _('instead of') + ' "' + article.toc_section + '")' + ' ' + registered_sections))
                # @article-type
                _sectitle = article.toc_section if fixed_sectitle is None else fixed_sectitle
                for item in article_utils.validate_article_type_and_section(article.article_type, _sectitle):
                    results.append(item)
        return (section_code, html_reports.tag('div', html_reports.validations_table(results)))

    def select_articles_to_convert(self, registered_articles, pkg_path=None, base_source_path=None):
        #actions = {'add': [], 'skip-update': [], 'update': [], '-': [], 'changed order': []}
        self.actions = {}
        for name in registered_articles.keys():
            if not name in self.pkg_articles.keys():
                self.actions[name] = '-'
                #self.complete_issue_items[name] = registered_articles[name]
        self.changed_orders = {}
        for name, article in self.pkg_articles.items():
            action = 'add'
            if name in registered_articles.keys():
                action = 'update'
                if pkg_path is not None and base_source_path is not None:
                    if fs_utils.read_file(base_source_path + '/' + name + '.xml') == fs_utils.read_file(pkg_path + '/' + name + '.xml'):
                        action = 'skip-update'
                if action == 'update':
                    if registered_articles[name].order != self.pkg_articles[name].order:
                        self.changed_orders[name] = (registered_articles[name].order, self.pkg_articles[name].order)
            self.actions[name] = action
            #if action == 'skip-update':
            #    self.complete_issue_items[name] = registered_articles[name]
            #else:
            #    self.complete_issue_items[name] = self.pkg_articles[name]

        unmatched_orders_errors = ''
        if self.changed_orders is not None:
            unmatched_orders_errors = ''.join([html_reports.p_message('WARNING: ' + _('orders') + ' ' + _('of') + ' ' + name + ': ' + ' -> '.join(list(order))) for name, order in self.changed_orders.items()])
        self.changed_orders_validations = ValidationsResults(unmatched_orders_errors)

    @property
    def issue_report(self):
        report = []
        if self.is_db_generation:
            if self.registered_issue_data_validations is not None:
                if self.registered_issue_data_validations.total > 0:
                    report.append(html_reports.tag('h2', 'Comparision of issue and articles data') + self.registered_issue_data_validations.report(True))
        self.evaluate_pkg_journal_and_issue_data_consistence()
        for item in [self.changed_orders_validations, self.pkg_data_consistence_validations]:
            if item is not None:
                if item.total > 0:
                    report.append(item.message)
        return ''.join(report) if len(report) > 0 else None

    @property
    def is_processed_in_batches(self):
        return any([self.is_aop_issue, self.is_rolling_pass])

    @property
    def is_aop_issue(self):
        return any([a.is_ahead for a in self.pkg_articles.values()])

    @property
    def is_rolling_pass(self):
        _is_rolling_pass = False
        if not self.is_aop_issue:
            epub_dates = list(set([a.epub_dateiso for a in self.pkg_articles.values() if a.epub_dateiso is not None]))

            epub_ppub_dates = [a.epub_ppub_dateiso for a in self.pkg_articles.values() if a.epub_ppub_dateiso is not None]
            collection_dates = [a.collection_dateiso for a in self.pkg_articles.values() if a.collection_dateiso is not None]
            other_dates = list(set(epub_ppub_dates + collection_dates))
            if len(epub_dates) > 0:
                if len(other_dates) == 0:
                    _is_rolling_pass = True
                elif len(other_dates) > 1:
                    _is_rolling_pass = True
                elif len([None for a in self.pkg_articles.values() if a.collection_dateiso is None]) > 0:
                    _is_rolling_pass = True
        return _is_rolling_pass

    @property
    def compiled_pkg_metadata(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        return self._compiled_pkg_metadata

    def compile_pkg_metadata(self):
        self.invalid_xml_name_items = []
        self._compiled_pkg_metadata = {label: {} for label in self.expected_equal_values + self.expected_unique_value}
        self.pkg_missing_items = {}

        for xml_name, article in self.pkg_articles.items():
            if article.tree is None:
                self.invalid_xml_name_items.append(xml_name)
            else:
                art_data = article.summary()
                for label in labels:
                    if art_data[label] is None:
                        if label in self.required_journal_data:
                            if not label in self.pkg_missing_items.keys():
                                self.pkg_missing_items[label] = []
                            self.pkg_missing_items[label].append(xml_name)
                    else:
                        self._compiled_pkg_metadata[label] = article_utils.add_new_value_to_index(self._compiled_pkg_metadata[label], art_data[label], xml_name)

    def evaluate_pkg_journal_and_issue_data_consistence(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        self.consistence_blocking_errors = 0

        r = ''
        if len(self.invalid_xml_name_items) > 0:
            r += html_reports.tag('div', html_reports.p_message('FATAL ERROR: ' + _('Invalid XML files.')))
            r += html_reports.tag('div', html_reports.format_list('', 'ol', self.invalid_xml_name_items, 'issue-problem'))
        for label, items in self.pkg_missing_items.items():
            r += html_reports.tag('div', html_reports.p_message('FATAL ERROR: ' + _('Missing') + ' ' + label + ' ' + _('in') + ':'))
            r += html_reports.tag('div', html_reports.format_list('', 'ol', items, 'issue-problem'))

        for label in self.expected_equal_values:
            if len(self._compiled_pkg_metadata[label]) > 1:
                _status = 'FATAL ERROR'
                if label == 'issue pub date':
                    if self.is_rolling_pass:
                        _status = 'WARNING'
                _m = _('same value for %s is required for all the documents in the package') % (label)
                part = html_reports.p_message(_status + ': ' + _m + '.')
                for found_value, xml_files in self._compiled_pkg_metadata[label].items():
                    part += html_reports.format_list(_('found') + ' ' + label + '="' + html_reports.display_xml(found_value, html_reports.XML_WIDTH*0.6) + '" ' + _('in') + ':', 'ul', xml_files, 'issue-problem')
                r += part

        for label in self.expected_unique_value:
            if len(self._compiled_pkg_metadata[label]) > 0 and len(self._compiled_pkg_metadata[label]) != len(self.pkg_articles):
                duplicated = {}
                for found_value, xml_files in self._compiled_pkg_metadata[label].items():
                    if len(xml_files) > 1:
                        duplicated[found_value] = xml_files

                if len(duplicated) > 0:
                    _m = _(': unique value of %s is required for all the documents in the package') % (label)
                    part = html_reports.p_message(error_level_for_unique[label] + _m)
                    if self.error_level_for_unique[label] == 'FATAL ERROR':
                        self.consistence_blocking_errors += 1
                    for found_value, xml_files in duplicated.items():
                        part += html_reports.format_list(_('found') + ' ' + label + '="' + found_value + '" ' + _('in') + ':', 'ul', xml_files, 'issue-problem')
                    r += part

        issue_common_data = ''

        for label in self.expected_equal_values:
            message = ''
            if len(self._compiled_pkg_metadata[label].items()) == 1:
                issue_common_data += html_reports.display_labeled_value(label, self._compiled_pkg_metadata[label].keys()[0])
            else:
                issue_common_data += html_reports.format_list(label, 'ol', self._compiled_pkg_metadata[label].keys())
                #issue_common_data += html_reports.p_message('FATAL ERROR: ' + _('Unique value expected for ') + label)

        pages = html_reports.tag('h2', 'Pages Report') + html_reports.tag('div', html_reports.sheet(['label', 'status', 'message'], self.pages(), table_style='validation', row_style='status'))

        toc_report = html_reports.tag('div', issue_common_data, 'issue-data') + html_reports.tag('div', r, 'issue-messages') + pages
        self.pkg_data_consistence_validations = ValidationsResults(toc_report)

    @property
    def pkg_journal_title(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        if len(self._compiled_pkg_metadata['journal-title']) > 0:
            return self._compiled_pkg_metadata['journal-title'].keys()[0]

    @property
    def pkg_issue_label(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        if len(self._compiled_pkg_metadata['issue label']) > 0:
            return self._compiled_pkg_metadata['issue label'].keys()[0]

    @property
    def pkg_e_issn(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        if len(self._compiled_pkg_metadata['e-ISSN']) > 0:
            return self._compiled_pkg_metadata['e-ISSN'].keys()[0]

    @property
    def pkg_p_issn(self):
        if self._compiled_pkg_metadata is None:
            self.compile_pkg_metadata()
        if len(self._compiled_pkg_metadata['print ISSN']) > 0:
            return self._compiled_pkg_metadata['print ISSN'].keys()[0]

    @property
    def selected_articles(self):
        _selected_articles = None
        if self.blocking_errors == 0:
            #utils.debugging('toc_f == 0')
            _selected_articles = {}
            for xml_name, status in self.actions.items():
                if status in ['add', 'update']:
                    _selected_articles[xml_name] = self.pkg_article[xml_name]
        return _selected_articles

    @property
    def compiled_affiliations(self):
        if self._compiled_affilitions is None:
            self._compiled_affilitions = self.compile_affiliations()
        return self._compiled_affilitions

    def compile_affiliations(self):
        evaluation = {}
        keys = [_('authors without aff'), 
                _('authors with more than 1 affs'), 
                _('authors with invalid xref[@ref-type=aff]'), 
                _('incomplete affiliations')]
        for k in keys:
            evaluation[k] = 0

        for xml_name, doc in self.pkg_articles.items():
            aff_ids = [aff.id for aff in doc.affiliations]
            for contrib in doc.contrib_names:
                if len(contrib.xref) == 0:
                    evaluation[_('authors without aff')] += 1
                elif len(contrib.xref) > 1:
                    valid_xref = [xref for xref in contrib.xref if xref in aff_ids]
                    if len(valid_xref) != len(contrib.xref):
                        evaluation[_('authors with invalid xref[@ref-type=aff]')] += 1
                    elif len(valid_xref) > 1:
                        evaluation[_('authors with more than 1 affs')] += 1
                    elif len(valid_xref) == 0:
                        evaluation[_('authors without aff')] += 1
            for aff in doc.affiliations:
                if None in [aff.id, aff.i_country, aff.norgname, aff.orgname, aff.city, aff.state, aff.country]:
                    evaluation[_('incomplete affiliations')] += 1
        return evaluation

    def compile_references(self):
        self.sources_and_reftypes = {}
        self.sources_at = {}
        self.reftype_and_sources = {}
        self.missing_source = []
        self.missing_year = []
        self.unusual_sources = []
        self.unusual_years = []
        for xml_name, doc in self.pkg_articles.items():
            for ref in doc.references:
                if not ref.source in self.sources_and_reftypes.keys():
                    self.sources_and_reftypes[ref.source] = {}
                if not ref.publication_type in self.sources_and_reftypes[ref.source].keys():
                    self.sources_and_reftypes[ref.source][ref.publication_type] = 0
                self.sources_and_reftypes[ref.source][ref.publication_type] += 1
                if not ref.source in self.sources_at.keys():
                    self.sources_at[ref.source] = []
                if not xml_name in self.sources_at[ref.source]:
                    self.sources_at[ref.source].append(ref.id + ' - ' + xml_name)
                if not ref.publication_type in self.reftype_and_sources.keys():
                    self.reftype_and_sources[ref.publication_type] = {}
                if not ref.source in self.reftype_and_sources[ref.publication_type].keys():
                    self.reftype_and_sources[ref.publication_type][ref.source] = 0
                self.reftype_and_sources[ref.publication_type][ref.source] += 1

                # year
                if ref.publication_type in attributes.BIBLIOMETRICS_USE:
                    if ref.year is None:
                        self.missing_year.append([ref.id, xml_name])
                    else:
                        numbers = len([n for n in ref.year if n.isdigit()])
                        not_numbers = len(ref.year) - numbers
                        if not_numbers > numbers:
                            self.unusual_years.append([ref.year, ref.id, xml_name])

                    if ref.source is None:
                        self.missing_source.append([ref.id, xml_name])
                    else:
                        numbers = len([n for n in ref.source if n.isdigit()])
                        not_numbers = len(ref.source) - numbers
                        if not_numbers < numbers:
                            self.unusual_sources.append([ref.source, ref.id, xml_name])
        self.bad_sources_and_reftypes = {source: reftypes for source, reftypes in self.sources_and_reftypes.items() if len(reftypes) > 1}

    def tabulate_languages(self):
        labels = ['name', 'toc section', '@article-type', 'article titles', 
            'abstracts', 'key words', '@xml:lang', 'versions']

        items = []
        for xml_name in self.xml_name_sorted_by_order:
            doc = self.pkg_articles[xml_name]
            values = []
            values.append(xml_name)
            values.append(doc.toc_section)
            values.append(doc.article_type)
            values.append(['[' + str(t.language) + '] ' + str(t.title) for t in doc.titles])
            values.append([t.language for t in doc.abstracts])
            k = {}
            for item in doc.keywords:
                if not item.get('l') in k.keys():
                    k[item.get('l')] = []
                k[item.get('l')].append(item.get('k'))
            values.append(k)
            values.append(doc.language)
            values.append(doc.trans_languages)
            items.append(label_values(labels, values))
        return (labels, items)

    def tabulate_elements_by_languages(self):
        labels = ['name', 'toc section', '@article-type', 'article titles, abstracts, key words', '@xml:lang', 'sub-article/@xml:lang']
        items = []
        for xml_name in self.xml_name_sorted_by_order:
            doc = self.pkg_articles[xml_name]
            lang_dep = {}
            for lang in doc.title_abstract_kwd_languages:

                elements = {}
                elem = doc.titles_by_lang.get(lang)
                if elem is not None:
                    elements['title'] = elem.title
                elem = doc.abstracts_by_lang.get(lang)
                if elem is not None:
                    elements['abstract'] = elem.text
                elem = doc.keywords_by_lang.get(lang)
                if elem is not None:
                    elements['keywords'] = [k.text for k in elem]
                lang_dep[lang] = elements

            values = []
            values.append(xml_name)
            values.append(doc.toc_section)
            values.append(doc.article_type)
            values.append(lang_dep)
            values.append(doc.language)
            values.append(doc.trans_languages)
            items.append(label_values(labels, values))
        return (labels, items)

    def tabulate_dates(self):
        labels = ['name', '@article-type', 
        'received', 'accepted', 'receive to accepted (days)', 'article date', 'issue date', 'accepted to publication (days)', 'accepted to today (days)']

        items = []
        for xml_name in self.xml_name_sorted_by_order:
            #utils.debugging(xml_name)
            doc = self.pkg_articles[xml_name]
            #utils.debugging(doc)
            values = []
            values.append(xml_name)

            #utils.debugging('doc.article_type')
            #utils.debugging(doc.article_type)
            values.append(doc.article_type)

            #utils.debugging('doc.received_dateiso')
            #utils.debugging(doc.received_dateiso)
            values.append(article_utils.display_date(doc.received_dateiso))

            #utils.debugging('doc.accepted_dateiso')
            #utils.debugging(doc.accepted_dateiso)
            values.append(article_utils.display_date(doc.accepted_dateiso))

            #utils.debugging('doc.history_days')
            #utils.debugging(doc.history_days)
            values.append(str(doc.history_days))

            #utils.debugging('doc.article_pub_dateiso')
            #utils.debugging(doc.article_pub_dateiso)
            values.append(article_utils.display_date(doc.article_pub_dateiso))

            #utils.debugging('doc.issue_pub_dateiso')
            #utils.debugging(doc.issue_pub_dateiso)
            values.append(article_utils.display_date(doc.issue_pub_dateiso))

            #utils.debugging('doc.publication_days')
            #utils.debugging(doc.publication_days)
            values.append(str(doc.publication_days))

            #utils.debugging('doc.registration_days')
            #utils.debugging(doc.registration_days)
            values.append(str(doc.registration_days))

            #utils.debugging(values)
            items.append(label_values(labels, values))
            #utils.debugging(items)

        return (labels, items)

    def pages(self):
        results = []
        previous_lpage = None
        previous_xmlname = None
        int_previous_lpage = None

        for xml_name in self.xml_name_sorted_by_order:
            #if self.pkg_articles[xml_name].is_rolling_pass or self.pkg_articles[xml_name].is_ahead:
            #else:
            fpage = self.pkg_articles[xml_name].fpage
            lpage = self.pkg_articles[xml_name].lpage
            msg = []
            status = ''
            if self.pkg_articles[xml_name].pages == '':
                msg.append(_('no pagination was found'))
                if not self.pkg_articles[xml_name].is_ahead:
                    status = 'ERROR'
            if fpage is not None and lpage is not None:
                if fpage.isdigit() and lpage.isdigit():
                    int_fpage = int(fpage)
                    int_lpage = int(lpage)

                    #if not self.pkg_articles[xml_name].is_rolling_pass and not self.pkg_articles[xml_name].is_ahead:
                    if int_previous_lpage is not None:
                        if int_previous_lpage > int_fpage:
                            status = 'FATAL ERROR' if not self.pkg_articles[xml_name].is_epub_only else 'WARNING'
                            msg.append(_('Invalid pages') + ': ' + _('check lpage={lpage} ({previous_article}) and fpage={fpage} ({xml_name})').format(previous_article=previous_xmlname, xml_name=xml_name, lpage=previous_lpage, fpage=fpage))
                        elif int_previous_lpage == int_fpage:
                            status = 'WARNING'
                            msg.append(_('lpage={lpage} ({previous_article}) and fpage={fpage} ({xml_name}) are the same').format(previous_article=previous_xmlname, xml_name=xml_name, lpage=previous_lpage, fpage=fpage))
                        elif int_previous_lpage + 1 < int_fpage:
                            status = 'WARNING'
                            msg.append(_('there is a gap between lpage={lpage} ({previous_article}) and fpage={fpage} ({xml_name})').format(previous_article=previous_xmlname, xml_name=xml_name, lpage=previous_lpage, fpage=fpage))
                    if int_fpage > int_lpage:
                        status = 'FATAL ERROR'
                        msg.append(_('Invalid page range'))
                    int_previous_lpage = int_lpage
                    previous_lpage = lpage
                    previous_xmlname = xml_name
            #dates = '|'.join([item if item is not None else 'none' for item in [self.pkg_articles[xml_name].epub_ppub_dateiso, self.pkg_articles[xml_name].collection_dateiso, self.pkg_articles[xml_name].epub_dateiso]])
            msg = '; '.join(msg)
            if len(msg) > 0:
                msg = '. ' + msg
            results.append({'label': xml_name, 'status': status, 'message': self.pkg_articles[xml_name].pages + msg})
        return results

    def validate_articles_pkg_xml_and_data(self, org_manager, doc_files_info_items, dtd_filesml_generation):
        #FIXME
        self.pkg_xml_structure_validations = PackageValidationsResults()
        self.pkg_xml_content_validations = PackageValidationsResults()

        for xml_name, doc_files_info in doc_files_info_items.items():
            for f in [doc_files_info.dtd_report_filename, doc_files_info.style_report_filename, doc_files_info.data_report_filename, doc_files_info.pmc_style_report_filename]:
                if os.path.isfile(f):
                    os.unlink(f)

        n = '/' + str(len(self.pkg_articles))
        index = 0

        utils.display_message('\n')
        utils.display_message(_('Validating XML files'))
        #utils.debugging('Validating package: inicio')
        for xml_name in self.xml_name_sorted_by_order:
            doc = self.pkg_articles[xml_name]
            doc_files_info = doc_files_info_items[xml_name]

            new_name = doc_files_info.new_name

            index += 1
            item_label = str(index) + n + ': ' + new_name
            utils.display_message(item_label)

            skip = False
            if self.actions is not None:
                skip = (self.actions[xml_name] == 'skip-update')

            if skip:
                utils.display_message(' -- skept')
            else:
                xml_filename = doc_files_info.new_xml_filename

                # XML structure validations
                xml_f, xml_e, xml_w = validate_article_xml(xml_filename, dtd_files, doc_files_info.dtd_report_filename, doc_files_info.style_report_filename, doc_files_info.ctrl_filename, doc_files_info.err_filename)
                report_content = ''
                for rep_file in [doc_files_info.err_filename, doc_files_info.dtd_report_filename, doc_files_info.style_report_filename]:
                    if os.path.isfile(rep_file):
                        report_content += extract_report_core(fs_utils.read_file(rep_file))
                        if is_xml_generation is False:
                            fs_utils.delete_file_or_folder(rep_file)
                data_validations = ValidationsResults(report_content)
                data_validations.fatal_errors = xml_f
                data_validations.errors = xml_e
                data_validations.warnings = xml_w
                self.pkg_xml_structure_validations.add(xml_name, data_validations)

                # XML Content validations
                report_content = article_reports.article_data_and_validations_report(org_manager, doc, new_name, os.path.dirname(xml_filename)ml_generation)
                data_validations = ValidationsResults(report_content)
                self.pkg_xml_content_validations.add(xml_name, data_validations)
                if is_xml_generation:
                    stats = html_reports.statistics_display(data_validations, False)
                    title = [_('Data Quality Control'), new_name]
                    html_reports.save(doc_files_info.data_report_filename, title, stats + report_content)

                #self.pkg_fatal_errors += xml_f + data_f
                #self.pkg_stats[xml_name] = ((xml_f, xml_e, xml_w), (data_f, data_e, data_w))
                #self.pkg_reports[xml_name] = (doc_files_info.err_filename, doc_files_info.style_report_filename, doc_files_info.data_report_filename)

        #utils.debugging('Validating package: fim')


class ArticlesPkgReport(object):

    def __init__(self, package):
        self.package = package

    def validate_consistency(self, validate_order):
        critical, toc_report = self.consistency_report(validate_order)
        toc_validations = ValidationsResults(toc_report)
        return (critical, toc_validations)

    def consistency_report(self, validate_order):
        critical = 0
        equal_data = ['journal-title', 'journal id NLM', 'e-ISSN', 'print ISSN', 'publisher name', 'issue label', 'issue pub date', ]
        unique_data = ['order', 'doi', 'elocation id', ]

        error_level_for_unique = {'order': 'FATAL ERROR', 'doi': 'FATAL ERROR', 'elocation id': 'FATAL ERROR', 'fpage-lpage-seq': 'FATAL ERROR'}
        required_data = ['journal-title', 'journal ISSN', 'publisher name', 'issue label', 'issue pub date', ]

        if not validate_order:
            error_level_for_unique['order'] = 'WARNING'

        if self.package.is_processed_in_batches:
            error_level_for_unique['fpage-lpage-seq'] = 'WARNING'
        else:
            unique_data += ['fpage-lpage-seq']

        invalid_xml_name_items, pkg_metadata, missing_data = self.package.journal_and_issue_metadata(equal_data + unique_data, required_data)

        r = ''

        if len(invalid_xml_name_items) > 0:
            r += html_reports.tag('div', html_reports.p_message('FATAL ERROR: ' + _('Invalid XML files.')))
            r += html_reports.tag('div', html_reports.format_list('', 'ol', invalid_xml_name_items, 'issue-problem'))
        for label, items in missing_data.items():
            r += html_reports.tag('div', html_reports.p_message('FATAL ERROR: ' + _('Missing') + ' ' + label + ' ' + _('in') + ':'))
            r += html_reports.tag('div', html_reports.format_list('', 'ol', items, 'issue-problem'))

        for label in equal_data:
            if len(pkg_metadata[label]) > 1:
                _status = 'FATAL ERROR'
                if label == 'issue pub date':
                    if self.package.is_rolling_pass:
                        _status = 'WARNING'
                _m = _('same value for %s is required for all the documents in the package') % (label)
                part = html_reports.p_message(_status + ': ' + _m + '.')
                for found_value, xml_files in pkg_metadata[label].items():
                    part += html_reports.format_list(_('found') + ' ' + label + '="' + html_reports.display_xml(found_value, html_reports.XML_WIDTH*0.6) + '" ' + _('in') + ':', 'ul', xml_files, 'issue-problem')
                r += part

        for label in unique_data:
            if len(pkg_metadata[label]) > 0 and len(pkg_metadata[label]) != len(self.package.articles):
                duplicated = {}
                for found_value, xml_files in pkg_metadata[label].items():
                    if len(xml_files) > 1:
                        duplicated[found_value] = xml_files

                if len(duplicated) > 0:
                    _m = _(': unique value of %s is required for all the documents in the package') % (label)
                    part = html_reports.p_message(error_level_for_unique[label] + _m)
                    if error_level_for_unique[label] == 'FATAL ERROR':
                        critical += 1
                    for found_value, xml_files in duplicated.items():
                        part += html_reports.format_list(_('found') + ' ' + label + '="' + found_value + '" ' + _('in') + ':', 'ul', xml_files, 'issue-problem')
                    r += part

        if validate_order:
            invalid_order = []
            for order, xml_files in pkg_metadata['order'].items():
                if order.isdigit():
                    if 0 < int(order) <= 99999:
                        pass
                    else:
                        critical += 1
                        invalid_order.append(xml_files)
                else:
                    critical += 1
                    invalid_order.append(xml_files)
            if len(invalid_order) > 0:
                r += html_reports.p_message('FATAL ERROR: ' + _('Invalid format of order. Expected number 1 to 99999.'))
                r += html_reports.format_list('order (article-id)', 'ol', invalid_order)

        issue_common_data = ''

        for label in equal_data:
            message = ''
            if len(pkg_metadata[label].items()) == 1:
                issue_common_data += html_reports.display_labeled_value(label, pkg_metadata[label].keys()[0])
            else:
                issue_common_data += html_reports.format_list(label, 'ol', pkg_metadata[label].keys())
                #issue_common_data += html_reports.p_message('FATAL ERROR: ' + _('Unique value expected for ') + label)

        pages = html_reports.tag('h2', 'Pages Report') + html_reports.tag('div', html_reports.sheet(['label', 'status', 'message'], self.package.pages(), table_style='validation', row_style='status'))

        return (critical, html_reports.tag('div', issue_common_data, 'issue-data') + html_reports.tag('div', r, 'issue-messages') + pages)


    def overview_report(self):
        r = ''

        r += html_reports.tag('h4', _('Languages overview'))
        labels, items = self.tabulate_elements_by_languages()
        r += html_reports.sheet(labels, items, 'dbstatus')

        r += html_reports.tag('h4', _('Dates overview'))
        labels, items = self.tabulate_dates()
        r += html_reports.sheet(labels, items, 'dbstatus')

        r += html_reports.tag('h4', _('Affiliations overview'))
        items = []
        affs_compiled = self.compile_affiliations()
        for label, q in affs_compiled.items():
            items.append({'label': label, 'quantity': str(q)})

        r += html_reports.sheet(['label', 'quantity'], items, 'dbstatus')
        return r

    def references_overview_report(self):

        if self.reftype_and_sources is None:
            self.compile_references()

        labels = ['label', 'status', 'message']
        items = []

        values = []
        values.append(_('references by type'))
        values.append('INFO')
        values.append({reftype: str(sum(sources.values())) for reftype, sources in self.reftype_and_sources.items()})
        items.append(label_values(labels, values))

        #message = {source: reftypes for source, reftypes in sources_and_reftypes.items() if len(reftypes) > 1}}
        if len(self.bad_sources_and_reftypes) > 0:
            values = []
            values.append(_('same sources as different types'))
            values.append('ERROR')
            values.append(self.bad_sources_and_reftypes)
            items.append(label_values(labels, values))
            values = []
            values.append(_('same sources as different types references'))
            values.append('INFO')
            values.append({source: self.sources_at.get(source) for source in self.bad_sources_and_reftypes.keys()})
            items.append(label_values(labels, values))

        if len(self.missing_source) > 0:
            items.append({'label': _('references missing source'), 'status': 'ERROR', 'message': [' - '.join(item) for item in self.missing_source]})
        if len(self.missing_year) > 0:
            items.append({'label': _('references missing year'), 'status': 'ERROR', 'message': [' - '.join(item) for item in self.missing_year]})
        if len(self.unusual_sources) > 0:
            items.append({'label': _('references with unusual value for source'), 'status': 'ERROR', 'message': [' - '.join(item) for item in self.unusual_sources]})
        if len(self.unusual_years) > 0:
            items.append({'label': _('references with unusual value for year'), 'status': 'ERROR', 'message': [' - '.join(item) for item in self.unusual_years]})

        return html_reports.tag('h4', _('Package references overview')) + html_reports.sheet(labels, items, table_style='dbstatus')

    def detail_report(self):
        labels = ['name', 'order', 'fpage', 'pagination', 'doi', 'aop pid', 'toc section', '@article-type', 'article title', 'reports']
        items = []

        n = '/' + str(len(self.pkg_articles))
        index = 0

        validations_text = ''

        #utils.debugging(self.pkg_stats)
        #utils.debugging(self.xml_name_sorted_by_order)
        utils.display_message('\n')
        utils.display_message(_('Generating Detail report'))
        for new_name in self.xml_name_sorted_by_order:
            index += 1
            item_label = str(index) + n + ': ' + new_name
            utils.display_message(item_label)

            a_name = 'view-reports-' + new_name
            links = '<a name="' + a_name + '"/>'
            status = ''
            block = ''

            if self.pkg_xml_structure_validations.item(new_name).total > 0:
                status = html_reports.statistics_display(self.pkg_xml_structure_validations.item(new_name))
                links += html_reports.report_link('xmlrep' + new_name, '[ ' + _('Structure Validations') + ' ]', 'xmlrep', a_name)
                links += html_reports.tag('span', status, 'smaller')
                block += html_reports.report_block('xmlrep' + new_name, self.pkg_xml_structure_validations.item(new_name).message, 'xmlrep', a_name)

            if self.pkg_xml_content_validations.item(new_name).total > 0:
                status = html_reports.statistics_display(self.pkg_xml_content_validations.item(new_name))
                links += html_reports.report_link('datarep' + new_name, '[ ' + _('Contents Validations') + ' ]', 'datarep', a_name)
                links += html_reports.tag('span', status, 'smaller')
                block += html_reports.report_block('datarep' + new_name, self.pkg_xml_content_validations.item(new_name).message, 'datarep', a_name)

            if self.is_db_generation:
                if self.registered_issue_data_validations is not None:
                    conversion_validations = self.registered_issue_data_validations.item(new_name)
                    if conversion_validations is not None:
                        if conversion_validations.total > 0:
                            status = html_reports.statistics_display(conversion_validations)
                            links += html_reports.report_link('xcrep' + new_name, '[ ' + _('Converter Validations') + ' ]', 'xcrep', a_name)
                            links += html_reports.tag('span', status, 'smaller')
                            block += html_reports.report_block('xcrep' + new_name, conversion_validations.message, 'xcrep', a_name)

            values = []
            values.append(new_name)
            values.append(self.pkg_articles[new_name].order)
            values.append(self.pkg_articles[new_name].fpage)
            values.append(self.pkg_articles[new_name].pages)

            values.append(self.pkg_articles[new_name].doi)
            values.append(self.pkg_articles[new_name].previous_pid)
            values.append(self.pkg_articles[new_name].toc_section)
            values.append(self.pkg_articles[new_name].article_type)
            values.append(self.pkg_articles[new_name].title)
            values.append(links)

            items.append(label_values(labels, values))
            items.append({'reports': block})

        return html_reports.sheet(labels, items, table_style='reports-sheet', html_cell_content=['reports'])

    def sources_overview_report(self):
        labels = ['source', 'total']
        h = None
        if len(self.reftype_and_sources) > 0:
            h = ''
            for reftype, sources in self.reftype_and_sources.items():
                items = []
                h += html_reports.tag('h4', reftype)
                for source in sorted(sources.keys()):
                    items.append({'source': source, 'total': str(sources[source])})
                h += html_reports.sheet(labels, items, 'dbstatus')
        return h


class PackageValidationsResults(object):

    def __init__(self, validations_results_items=None):
        if validations_results_items is None:
            self.validations_results_items = {}
        else:
            self.validations_results_items = validations_results_items

    def item(self, name):
        if self.validations_results_items is not None:
            return self.validations_results_items.get(name)

    def add(self, name, validations_results):
        self.validations_results_items[name] = validations_results

    @property
    def total(self):
        return sum([item.total for item in self.validations_results_items.values()])

    @property
    def fatal_errors(self):
        return sum([item.fatal_errors for item in self.validations_results_items.values()])

    def report(self, errors_only=False):
        _reports = ''
        if self.validations_results_items is not None:
            for xml_name, results in self.validations_results_items.items():
                if results.total > 0 or errors_only is False:
                    _reports += html_reports.tag('h4', xml_name)
                    _reports += results.message
        return _reports


class ValidationsResults(object):

    def __init__(self, message):
        self.fatal_errors, self.errors, self.warnings = html_reports.statistics_numbers(message)
        self.message = message

    @property
    def total(self):
        return sum([self.fatal_errors, self.errors, self.warnings])


def register_log(text):
    log_items.append(datetime.now().isoformat() + ' ' + text)


def update_err_filename(err_filename, dtd_report):
    if os.path.isfile(dtd_report):
        separator = ''
        if os.path.isfile(err_filename):
            separator = '\n\n\n' + '.........\n\n\n'
        open(err_filename, 'a+').write(separator + 'DTD errors\n' + '-'*len('DTD errors') + '\n' + open(dtd_report, 'r').read())


def delete_irrelevant_reports(ctrl_filename, is_valid_style, dtd_validation_report, style_checker_report):
    if ctrl_filename is None:
        if is_valid_style is True:
            os.unlink(style_checker_report)
    else:
        open(ctrl_filename, 'w').write('Finished')
    if os.path.isfile(dtd_validation_report):
        os.unlink(dtd_validation_report)


def validate_article_xml(xml_filename, dtd_files, dtd_report, style_report, ctrl_filename, err_filename):

    xml, valid_dtd, valid_style = xpchecker.validate_article_xml(xml_filename, dtd_files, dtd_report, style_report)
    f, e, w = valid_style
    update_err_filename(err_filename, dtd_report)
    if xml is None:
        f += 1
    if not valid_dtd:
        f += 1
    delete_irrelevant_reports(ctrl_filename, f + e + w == 0, dtd_report, style_report)
    return (f, e, w)


def extract_report_core(content):
    report = ''
    if 'Parse/validation finished' in content and '<!DOCTYPE' in content:
        part1 = content[0:content.find('<!DOCTYPE')]
        part2 = content[content.find('<!DOCTYPE'):]

        l = part1[part1.rfind('Line number:')+len('Line number:'):]
        l = l[0:l.find('Column')]
        l = ''.join([item.strip() for item in l.split()])
        if l.isdigit():
            l = str(int(l) + 1) + ':'
            if l in part2:
                part2 = part2[0:part2.find(l)] + '\n...'

        part1 = part1.replace('\n', '<br/>')
        part2 = part2.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br/>').replace('\t', '&nbsp;'*4)
        report = part1 + part2
    elif '</body>' in content:
        if not isinstance(content, unicode):
            content = content.decode('utf-8')
        content = content[content.find('<body'):]
        content = content[0:content.rfind('</body>')]
        report = content[content.find('>')+1:]
    elif '<body' in content:
        if not isinstance(content, unicode):
            content = content.decode('utf-8')
        content = content[content.find('<body'):]
        report = content[content.find('>')+1:]
    return report


def sum_stats(stats_items):
    f = sum([i[0] for i in stats_items])
    e = sum([i[1] for i in stats_items])
    w = sum([i[2] for i in stats_items])
    return (f, e, w)


def xml_list(pkg_path, xml_filenames=None):
    r = ''
    r += '<p>' + _('XML path') + ': ' + pkg_path + '</p>'
    if xml_filenames is None:
        xml_filenames = [pkg_path + '/' + name for name in os.listdir(pkg_path) if name.endswith('.xml')]
    r += '<p>' + _('Total of XML files') + ': ' + str(len(xml_filenames)) + '</p>'
    r += html_reports.format_list('', 'ol', [os.path.basename(f) for f in xml_filenames])
    return '<div class="xmllist">' + r + '</div>'


def error_msg_subtitle():
    msg = html_reports.tag('p', _('Fatal error - indicates errors which impact on the quality of the bibliometric indicators and other services'))
    msg += html_reports.tag('p', _('Error - indicates the other kinds of errors'))
    msg += html_reports.tag('p', _('Warning - indicates that something can be an error or something needs more attention'))
    return html_reports.tag('div', msg, 'subtitle')


def label_values(labels, values):
    r = {}
    for i in range(0, len(labels)):
        r[labels[i]] = values[i]
    return r


def articles_sorted_by_order(articles):
    sorted_by_order = {}
    for xml_name, article in articles.items():
        try:
            _order = article.order
        except:
            _order = 'None'
        if not _order in sorted_by_order.keys():
            sorted_by_order[_order] = []
        sorted_by_order[_order].append(article)
    return sorted_by_order


def sorted_xml_name_by_order(articles):
    order_and_xml_name_items = {}
    for xml_name, article in articles.items():
        if article.tree is None:
            _order = 'None'
        else:
            _order = article.order
        if not _order in order_and_xml_name_items.keys():
            order_and_xml_name_items[_order] = []
        order_and_xml_name_items[_order].append(xml_name)

    sorted_items = []
    for order in sorted(order_and_xml_name_items.keys()):
        for item in order_and_xml_name_items[order]:
            sorted_items.append(item)
    return sorted_items


def processing_result_location(result_path):
    return '<h5>' + _('Result of the processing:') + '</h5>' + '<p>' + html_reports.link('file:///' + result_path, result_path) + '</p>'


def save_report(filename, title, content, xpm_version=None):
    if xpm_version is not None:
        content += html_reports.tag('p', _('report generated by XPM ') + xpm_version)
    html_reports.save(filename, title, content)
    utils.display_message('\n\nReport:' + '\n ' + filename)


def display_report(report_filename):
    try:
        os.system('python -mwebbrowser file:///' + report_filename.replace('//', '/').encode(encoding=sys.getfilesystemencoding()))
    except:
        pass


def format_complete_report(report_components):
    content = ''
    order = ['xml-files', 'summary-report', 'issue-report', 'detail-report', 'conversion-report', 'pkg_overview', 'db-overview', 'issue-not-registered', 'toc', 'references']
    labels = {
        'issue-report': 'journal/issue',
        'summary-report': _('Summary report'), 
        'detail-report': _('XML Validations report'), 
        'conversion-report': _('Conversion report'),
        'xml-files': _('Files/Folders'),
        'db-overview': _('Database'),
        'pkg_overview': _('Package overview'),
        'references': _('Sources')
    }
    validations = ValidationsResults(html_reports.join_texts(report_components.values()))
    report_components['summary-report'] = error_msg_subtitle() + html_reports.statistics_display(validations, False) + report_components.get('summary-report', '')

    content += html_reports.tabs_items([(tab_id, labels[tab_id]) for tab_id in order if report_components.get(tab_id) is not None], 'summary-report')
    for tab_id in order:
        c = report_components.get(tab_id)
        if c is not None:
            style = 'selected-tab-content' if tab_id == 'summary-report' else 'not-selected-tab-content'
            content += html_reports.tab_block(tab_id, c, style)

    content += html_reports.tag('p', _('finished'))
    validations.message = label_errors(content)
    return validations


def label_errors_type(content, error_type, prefix):
    new = []
    i = 0
    content = content.replace(error_type, '~BREAK~' + error_type)
    for part in content.split('~BREAK~'):
        if part.startswith(error_type):
            i += 1
            part = part.replace(error_type, error_type + ' [' + prefix + str(i) + ']')
        new.append(part)
    return ''.join(new)


def label_errors(content):
    content = content.replace('ERROR', '[ERROR')
    content = content.replace('FATAL [ERROR', 'FATAL ERROR')
    content = label_errors_type(content, 'FATAL ERROR', 'F')
    content = label_errors_type(content, '[ERROR', 'E')
    content = label_errors_type(content, 'WARNING', 'W')
    content = content.replace('[ERROR', 'ERROR')
    return content


def join_reports(reports, errors_only=False):
    _reports = ''
    if reports is not None:
        for xml_name, results in reports.items():
            if results.total > 0 or errors_only is False:
                _reports += html_reports.tag('h4', xml_name)
                _reports += results.message
    return _reports



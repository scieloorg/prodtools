# coding=utf-8
import os
import shutil
from datetime import datetime

import xml_utils
import article_utils
import article_validations
import reports

from article import Article, PersonAuthor, CorpAuthor, format_author


html_report = reports.ReportHTML()


class TOCReport(object):

    def __init__(self, articles, validate_order):
        self.articles = articles
        self.validate_order = validate_order

    def report(self):
        invalid = []
        equal_data = ['journal-title', 'journal id NLM', 'journal ISSN', 'publisher name', 'issue label', 'issue pub date', ]
        unique_data = ['order', 'doi', 'elocation id']
        unique_status = {'order': 'FATAL ERROR', 'doi': 'FATAL ERROR', 'elocation id': 'FATAL ERROR', 'fpage-and-seq': 'ERROR'}

        if not self.validate_order:
            unique_status['order'] = 'WARNING'

        toc_data = {}
        for label in equal_data + unique_data:
            toc_data[label] = {}

        for xml_name, article in self.articles.items():
            if article is None:
                invalid.append(xml_name)
            else:
                art_data = article.summary()
                for label in toc_data.keys():
                    toc_data[label] = article_utils.add_new_value_to_index(toc_data[label], art_data[label], xml_name)

        r = ''
        if len(invalid) > 0:
            r += html_report.tag('div', html_report.format_message('FATAL ERROR: Invalid XML files'))
            r += html_report.tag('div', html_report.format_list('', 'ol', invalid, 'issue-problem'))

        for label in equal_data:
            if len(toc_data[label]) > 1:
                part = html_report.format_message('FATAL ERROR: same value for ' + label + ' is required for all the articles of the package')
                for found_value, xml_files in toc_data[label].items():
                    part += html_report.format_list('found ' + label + ' "' + html_report.display_xml(found_value) + '" in:', 'ul', xml_files, 'issue-problem')
                r += part

        for label in unique_data:
            if len(toc_data[label]) > 0 and len(toc_data[label]) != len(self.articles):
                none = []
                duplicated = {}
                pages = {}
                for found_value, xml_files in toc_data[label].items():
                    if found_value == 'None':
                        none = xml_files
                    else:
                        if len(xml_files) > 1:
                            duplicated[found_value] = xml_files
                        if label == 'fpage-and-seq':
                            v = found_value
                            if v.isdigit():
                                v = str(int(found_value))
                            if not v in pages.keys():
                                pages[v] = []
                            pages[v] += xml_files

                if len(pages) == 1 and '0' in pages.keys():
                    duplicated = []

                if len(duplicated) > 0:
                    part = html_report.format_message(unique_status[label] + ': unique value of ' + label + ' is required for all the articles of the package')
                    for found_value, xml_files in duplicated.items():
                        part += html_report.format_list('found ' + label + ' "' + found_value + '" in:', 'ul', xml_files, 'issue-problem')
                    r += part
                if len(none) > 0:
                    part = html_report.format_message('INFO: there is no value for ' + label + '.')
                    part += html_report.format_list('no value for ' + label + ' in:', 'ul', none, 'issue-problem')
                    r += part

        issue_common_data = ''
        for label in equal_data:
            message = ''
            if len(toc_data[label].items()) == 1:
                issue_common_data += html_report.display_labeled_value(label, toc_data[label].keys()[0])
            else:
                message = '(ERROR: Unique value expected for ' + label + ')'
                issue_common_data += html_report.format_list(label + message, 'ol', toc_data[label].keys())
        return html_report.tag('div', issue_common_data, 'issue-data') + html_report.tag('div', r, 'issue-messages')


class ArticleDisplayReport(object):

    def __init__(self, article, sheet_data, xml_path, xml_name):
        self.article = article
        self.xml_name = xml_name
        self.xml_path = xml_path
        self.files = package_files(xml_path, xml_name)
        self.sheet_data = sheet_data

    @property
    def summary(self):
        return self.issue_header + self.article_front

    @property
    def article_front(self):
        r = self.xml_name + ' is invalid.'
        if self.article is not None:
            r = ''
            r += self.language
            r += self.toc_section
            r += self.article_type
            r += self.display_titles()
            r += self.doi
            r += self.article_id_other
            r += self.article_previous_id
            r += self.order
            r += self.fpage
            r += self.fpage_seq
            r += self.elocation_id
            r += self.article_dates
            r += self.contrib_names
            r += self.contrib_collabs
            r += self.affiliations
            r += self.abstracts
            r += self.keywords

        return html_report.tag('h2', 'Article front') + html_report.tag('div', r, 'article-data')

    @property
    def article_body(self):
        r = ''
        r += self.sections
        r += self.formulas
        r += self.tables
        return html_report.tag('h2', 'Article body') + html_report.tag('div', r, 'article-data')

    @property
    def article_back(self):
        r = ''
        r += self.funding
        r += self.footnotes
        return html_report.tag('h2', 'Article back') + html_report.tag('div', r, 'article-data')

    @property
    def files_and_href(self):
        r = ''
        r += html_report.tag('h2', 'Files in the package') + html_report.sheet(self.sheet_data.package_files(self.files))
        r += html_report.tag('h2', '@href') + html_report.sheet(self.sheet_data.hrefs_sheet_data(self.xml_path))
        return r

    @property
    def authors_sheet(self):
        return html_report.tag('h2', 'Authors') + html_report.sheet(self.sheet_data.authors_sheet_data())

    @property
    def sources_sheet(self):
        return html_report.tag('h2', 'Sources') + html_report.sheet(self.sheet_data.sources_sheet_data())

    def display_labeled_value(self, label, value, style=''):
        return html_report.display_labeled_value(label, value, style)

    def display_titles(self):
        r = ''
        for title in self.article.titles:
            r += html_report.display_labeled_value(title.language, title.title)
        return r

    def display_text(self, label, items):
        r = html_report.tag('p', label, 'label')
        for item in items:
            r += self.display_labeled_value(item.language, item.text)
        return html_report.tag('div', r)

    @property
    def language(self):
        return self.display_labeled_value('@xml:lang', self.article.language)

    @property
    def toc_section(self):
        return self.display_labeled_value('toc section', self.article.toc_section, 'toc-section')

    @property
    def article_type(self):
        return self.display_labeled_value('@article-type', self.article.article_type, 'article-type')

    @property
    def article_dates(self):
        return self.display_labeled_value('date(epub-ppub)', article_utils.format_date(self.article.epub_ppub_date)) + self.display_labeled_value('date(epub)', article_utils.format_date(self.article.epub_date)) + self.display_labeled_value('date(collection)', article_utils.format_date(self.article.collection_date))

    @property
    def contrib_names(self):
        return html_report.format_list('authors:', 'ol', [format_author(a) for a in self.article.contrib_names])

    @property
    def contrib_collabs(self):
        r = [a.collab for a in self.article.contrib_collabs]
        if len(r) > 0:
            r = html_report.format_list('collabs', 'ul', r)
        else:
            r = self.display_labeled_value('collabs', 'None')
        return r

    @property
    def abstracts(self):
        return self.display_text('abstracts', self.article.abstracts)

    @property
    def keywords(self):
        return html_report.format_list('keywords:', 'ol', ['(' + k['l'] + ') ' + k['k'] for k in self.article.keywords])

    @property
    def order(self):
        return self.display_labeled_value('order', self.article.order, 'order')

    @property
    def doi(self):
        return self.display_labeled_value('doi', self.article.doi, 'doi')

    @property
    def fpage(self):
        r = self.display_labeled_value('fpage', self.article.fpage, 'fpage')
        r += self.display_labeled_value('lpage', self.article.fpage, 'lpage')
        return r

    @property
    def fpage_seq(self):
        return self.display_labeled_value('fpage/@seq', self.article.fpage_seq, 'fpage')

    @property
    def elocation_id(self):
        return self.display_labeled_value('elocation-id', self.article.elocation_id, 'fpage')

    @property
    def funding(self):
        r = self.display_labeled_value('ack', self.article.ack_xml)
        r += self.display_labeled_value('fn[@fn-type="financial-disclosure"]', self.article.financial_disclosure, 'fpage')
        return r

    @property
    def article_id_other(self):
        return self.display_labeled_value('article-id (other)', self.article.article_id_other)

    @property
    def article_previous_id(self):
        return self.display_labeled_value('previous article id', self.article.article_previous_id)

    @property
    def sections(self):
        _sections = ['[' + sec_id + '] ' + sec_title + ' (' + str(sec_type) + ')' for sec_id, sec_type, sec_title in self.article.article_sections]
        return html_report.format_list('sections:', 'ul', _sections)

    @property
    def formulas(self):
        r = html_report.tag('p', 'disp-formulas:', 'label')
        for item in self.article.formulas:
            r += html_report.tag('p', item)
        return r

    @property
    def footnotes(self):
        r = ''
        for item in self.article.article_fn_list:
            scope, fn_xml = item
            r += html_report.tag('p', scope, 'label')
            r += html_report.tag('p', fn_xml)
        if len(r) > 0:
            r = html_report.tag('p', 'foot notes:', 'label') + r
        return r

    @property
    def issue_header(self):
        if self.article is not None:
            r = [self.article.journal_title, self.article.journal_id_nlm_ta, self.article.issue_label, article_utils.format_date(self.article.issue_pub_date)]
            return html_report.tag('div', '\n'.join([html_report.tag('h5', item) for item in r if item is not None]), 'issue-data')
        else:
            return ''

    @property
    def tables(self):
        r = html_report.tag('p', 'Tables:', 'label')
        for t in self.article.tables:
            header = html_report.tag('h3', t.id)
            table_data = ''
            table_data += html_report.display_labeled_value('label', t.label, 'label')
            table_data += html_report.display_labeled_value('caption',  t.caption, 'label')
            table_data += html_report.tag('p', 'table-wrap/table (xml)', 'label')
            table_data += html_report.tag('div', html_report.html_value(t.table), 'xml')
            if t.table:
                table_data += html_report.tag('p', 'table-wrap/table', 'label')
                table_data += html_report.tag('div', t.table, 'element-table')
            if t.graphic:
                table_data += html_report.display_labeled_value('table-wrap/graphic', t.graphic.display('file:///' + self.xml_path), 'value')
            r += header + html_report.tag('div', table_data, 'block')
        return r

    @property
    def affiliations(self):
        r = html_report.tag('p', 'Affiliations:', 'label')
        for item in self.article.affiliations:
            r += html_report.tag('p', html_report.html_value(item.xml))
        r += html_report.sheet(self.sheet_data.affiliations_sheet_data())
        return r

    @property
    def id_and_xml_list(self):
        sheet_data = []
        t_header = ['@id', 'xml']
        for item in self.article.elements_which_has_id_attribute:
            row = {}
            row['@id'] = item.attrib.get('id')
            row['xml'] = xml_utils.node_xml(item)
            row['xml'] = row['xml'][0:row['xml'].find('>')+1]
            sheet_data.append(row)
        r = html_report.tag('h2', 'elements and @id:')
        r += html_report.sheet((t_header, [], sheet_data))
        return r

    @property
    def id_and_tag_list(self):
        sheet_data = []
        t_header = ['@id', 'tag']
        for item in self.article.elements_which_has_id_attribute:
            row = {}
            row['@id'] = item.attrib.get('id')
            row['tag'] = item.tag
            sheet_data.append(row)
        r = html_report.tag('h2', 'elements and @id:')
        r += html_report.sheet((t_header, [], sheet_data))
        return r


class ArticleValidationReport(object):

    def __init__(self, article_validation, display_problems):
        self.article_validation = article_validation
        self.display_problems = display_problems

    def display_items(self, items):
        r = ''
        for item in items:
            r += self.display_item(item)
        return r

    def display_item(self, item):
        return html_report.format_message(item)

    def format_table(self, content):
        r = '<p>'
        r += '<table class="validation">'
        r += '<thead>'
        r += '<tr>'
        for label in ['label', 'status', 'message/value']:
            r += '<th class="th">' + label + '</th>'
        r += '</tr></thead>'
        r += '<tbody>' + content + '</tbody>'
        r += '</table></p>'
        return r

    def format_row(self, label, status, message):
        r = ''
        cell = ''
        display = (self.display_problems is False)
        if not display:
            display = status in ['FATAL ERROR', 'ERROR', 'WARNING', 'INFO']
        if display:
            cell += html_report.tag('td', label, 'td_label')
            cell += html_report.tag('td', status, 'td_status')
            style = html_report.message_style(status + ':')
            value = message
            if '<' in value and '>' in value:
                value = html_report.display_xml(value)
            if style == 'ok':
                value = html_report.tag('span', value, 'value')
            cell += html_report.tag('td', value, 'td_message')
            r += html_report.tag('tr', cell, style)
        return r

    def get_rows(self, label_status_message_list):
        r = ''
        if isinstance(label_status_message_list, list):
            for item in label_status_message_list:
                r += self.get_rows(item)
        else:
            label, status, message = label_status_message_list
            r += self.format_row(label, status, message)
        return r

    def report_results(self, display_problems):
        if display_problems:
            self.display_problems = display_problems
        rows = ''
        items = [self.article_validation.journal_title,
                    self.article_validation.publisher_name,
                    self.article_validation.journal_id,
                    self.article_validation.journal_id_nlm_ta,
                    self.article_validation.journal_issns,
                    self.article_validation.issue_label,
                    self.article_validation.language,
                    self.article_validation.article_type,
                    self.article_validation.article_date_types,
                    self.article_validation.toc_section,
                    self.article_validation.order,
                    self.article_validation.doi,
                    self.article_validation.pagination,
                    self.article_validation.total_of_pages,
                    self.article_validation.total_of_equations,
                    self.article_validation.total_of_tables,
                    self.article_validation.total_of_figures,
                    self.article_validation.total_of_references,
                    self.article_validation.titles,
                    self.article_validation.contrib_names,
                    self.article_validation.contrib_collabs,
                    self.article_validation.affiliations,
                    self.article_validation.funding,
                    self.article_validation.license_text,
                    self.article_validation.license_url,
                    self.article_validation.license_type,
                    self.article_validation.history,
                    self.article_validation.abstracts,
                    self.article_validation.keywords,
                    self.article_validation.xref_rids,
                ]
        rows = self.format_table(rows)
        rows += self.references
        return html_report.tag('div', html_report.tag('h2', 'Validations') + rows, 'article-messages')

    @property
    def references(self):
        rows = ''
        for ref in self.article_validation.references:
            ref_result = ref.evaluate()
            result = self.get_rows(ref_result)
            if len(result) > 0:
                rows += html_report.tag('h3', 'Reference ' + ref.id)
                rows += html_report.display_xml(ref.reference.xml)
                rows += self.format_table(result)
        return rows


class ArticleSheetData(object):

    def __init__(self, article, article_validation):
        self.article = article
        self.article_validation = article_validation

    def authors_sheet_data(self, filename=None):
        r = []
        t_header = ['xref', 'given-names', 'surname', 'suffix', 'prefix', 'collab', 'role']
        if not filename is None:
            t_header = ['filename', 'scope'] + t_header
        for a in self.article.contrib_names:
            row = {}
            row['scope'] = 'article meta'
            row['filename'] = filename
            row['xref'] = ' '.join(a.xref)
            row['given-names'] = a.fname
            row['surname'] = a.surname
            row['suffix'] = a.suffix
            row['prefix'] = a.prefix
            row['role'] = a.role
            r.append(row)

        for a in self.article.contrib_collabs:
            row = {}
            row['scope'] = 'article meta'
            row['filename'] = filename
            row['collab'] = a.collab
            row['role'] = a.role
            r.append(row)

        for ref in self.article.references:
            for item in ref.authors_list:
                row = {}
                row['scope'] = ref.id
                row['filename'] = filename
                if isinstance(item, PersonAuthor):
                    row['given-names'] = item.fname
                    row['surname'] = item.surname
                    row['suffix'] = item.suffix
                    row['prefix'] = item.prefix
                    row['role'] = item.role
                elif isinstance(item, CorpAuthor):
                    row['collab'] = item.collab
                    row['role'] = item.role
                else:
                    row['given-names'] = '?'
                    row['surname'] = '?'
                    row['suffix'] = '?'
                    row['prefix'] = '?'
                    row['role'] = '?'
                r.append(row)
        return (t_header, [], r)

    def sources_sheet_data(self, filename=None):
        r = []
        t_header = ['ID', 'type', 'year', 'source', 'publisher name', 'location', ]
        if not filename is None:
            t_header = ['filename', 'scope'] + t_header

        for ref in self.article.references:
            row = {}
            row['scope'] = ref.id
            row['ID'] = ref.id
            row['filename'] = filename
            row['type'] = ref.publication_type
            row['year'] = ref.year
            row['source'] = ref.source
            row['publisher name'] = ref.publisher_name
            row['location'] = ref.publisher_loc
            r.append(row)
        return (t_header, [], r)

    def tables_sheet_data(self, path):
        t_header = ['ID', 'label/caption', 'table/graphic']
        r = []
        for t in self.article.tables:
            row = {}
            row['ID'] = t.graphic_parent.id
            row['label/caption'] = t.graphic_parent.label + '/' + t.graphic_parent.caption
            row['table/graphic'] = t.table + t.graphic_parent.graphic.display('file:///' + path)
            r.append(row)
        return (t_header, ['label/caption', 'table/graphic'], r)

    def hrefs_sheet_data(self, path):
        t_header = ['href', 'display', 'xml']
        r = []

        for item in self.article.hrefs:
            row = {}
            row['href'] = item.src
            msg = ''
            if item.is_internal_file:
                if not os.path.isfile(path + '/' + item.src) and not os.path.isfile(path + '/' + item.src + '.jpg'):
                    msg = 'ERROR: ' + item.src + ' not found in package'
                row['display'] = item.display('file:///' + path) + '<p>' + msg + '</p>'
            else:
                if not article_utils.url_check(item.src):
                    msg = 'ERROR: ' + item.src + ' is not working'
                row['display'] = item.display(item.src) + '<p>' + msg + '</p>'
            row['xml'] = item.xml
            r.append(row)
        return (t_header, ['display', 'xml'], r)

    def package_files(self, files):
        t_header = ['files', 'status']
        r = []
        inxml = [item.src for item in self.article.hrefs]

        for item in files:
            row = {}
            row['files'] = item
            if item in inxml:
                status = 'found in XML'
            else:
                if item.endswith('.jpg'):
                    if item[:-4] in inxml:
                        status = 'found in XML'
                    else:
                        status = 'WARNING: not found in XML'
                else:
                    status = 'WARNING: not found in XML'
            row['status'] = status
            r.append(row)
        return (t_header, ['files', 'status'], r)

    def affiliations_sheet_data(self):
        t_header = ['aff id', 'aff orgname', 'aff norgname', 'aff orgdiv1', 'aff orgdiv2', 'aff country', 'aff city', 'aff state', ]
        r = []
        for a in self.article.affiliations:
            row = {}
            row['aff id'] = a.id
            row['aff norgname'] = a.norgname
            row['aff orgname'] = a.orgname
            row['aff orgdiv1'] = a.orgdiv1
            row['aff orgdiv2'] = a.orgdiv2
            row['aff city'] = a.city
            row['aff state'] = a.state
            row['aff country'] = a.country
            r.append(row)
        return (t_header, ['aff xml'], r)


def package_files(path, xml_name):
    r = []
    for item in os.listdir(path):
        if not item.endswith('.xml'):
            prefix = xml_name.replace('.xml', '')
            if item.startswith(prefix + '.') or item.startswith(prefix + '-') or item.startswith(prefix + '_'):
                r.append(item)
    return r


def toc_report_data(articles_and_filenames, validate_order):
    toc_report_content = TOCReport(articles_and_filenames, validate_order).report()
    toc_f, toc_e, toc_w = reports.statistics_numbers(toc_report_content)
    return (toc_f, toc_e, toc_w, toc_report_content)


def _validate_article_data(article, new_name, package_path, validate_order, display_sheets):
    if article is None:
        content = 'FATAL ERROR: Unable to get data of ' + new_name + '.'
        sheet_data = None
    else:
        article_validation = article_validations.ArticleContentValidation(article, validate_order)
        sheet_data = ArticleSheetData(article, article_validation)
        article_display_report = ArticleDisplayReport(article, sheet_data, package_path, new_name)
        article_validation_report = ArticleValidationReport(article_validation, False)
        content = article_report_content(article_display_report, article_validation_report, display_sheets)

    return (content, sheet_data)


def validate_article_data(article, new_name, package_path, report_filename, validate_order, display_sheets):
    content, sheet_data = _validate_article_data(article, new_name, package_path, validate_order, display_sheets)
    f, e, w = reports.statistics_numbers(content)
    stats = html_report.statistics_messages(f, e, w, '')

    html_report.title = ['Contents validations required by SciELO ', new_name]
    html_report.body = stats + content
    html_report.save(report_filename)
    return (f, e, w, sheet_data)


def article_report_content(data_display, data_validation, display_sheets):
    content = ''
    #content += data_display.summary
    content += data_validation.report_results(True)
    #content += data_display.article_back
    #content += data_display.article_body
    content += data_display.files_and_href
    content += data_display.id_and_tag_list
    if display_sheets:
        content += data_display.authors_sheet
        content += data_display.sources_sheet
    return content


def example():
    xml_path = '/Users/robertatakenaka/Documents/vm_dados/scielo_data/serial/pab/v48n7/markup_xml/scielo_package'
    report_path = '/Users/robertatakenaka/Documents/vm_dados/scielo_data/_xpm_reports_'
    report_filenames = {v:v.replace('.xml', '') for v in os.listdir(xml_path) if v.endswith('.xml') and not 'incorre' in v }
    generate_contents_reports(xml_path, report_path, report_filenames)
    print('Reports in ' + report_path)
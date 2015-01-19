# coding=utf-8

import os

import xml_utils
import article_reports
import xpchecker
import html_reports

from article import Article


html_report = html_reports.ReportHTML()


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


def validate_article_xml(new_name, xml_filename, dtd_files, dtd_report, style_report, ctrl_filename, err_filename):
    xml, valid_dtd, valid_style = xpchecker.validate_article_xml(xml_filename, dtd_files, dtd_report, style_report)
    f, e, w = valid_style
    update_err_filename(err_filename, dtd_report)
    delete_irrelevant_reports(ctrl_filename, f + e + w == 0, dtd_report, style_report)
    if xml is None:
        f += 1
    if not valid_dtd:
        w += 1
    return (f, e, w)


def validate_article_data(article, new_name, package_path, report_filename, validate_order, display_sheets):
    f, e, w, sheet_data = article_reports.validate_article_data(article, new_name, package_path, report_filename, validate_order, display_sheets)
    return (f, e, w, sheet_data)


def article_validations_text(filename):
    content = ''
    if os.path.isfile(filename):
        content = open(filename, 'r').read()
        if '</article>' in content:
            content = html_report.display_xml(content)
            content = content.replace('\n', '<br/>')

        if '</html>' in content:
            content = content[content.find('<body'):]
            content = content[0:content.rfind('</body>')]
            content = content[content.find('>')+1:]
    if len(content) > 0:
        content = '<p class="issue-data">content of ' + filename + '</p>' + content
    return content


def sum_stats(stats_items):
    f = sum([i[0] for i in stats_items])
    e = sum([i[1] for i in stats_items])
    w = sum([i[2] for i in stats_items])
    return (f, e, w)


def xml_list(pkg_path, xml_filenames):
    r = ''
    r += '<h2>XML files</h2>'
    r += '<p>XML path: ' + pkg_path + '</p>'
    r += '<p>Total of XML files: ' + str(len(xml_filenames)) + '</p>'
    r += html_report.format_list('', 'ol', [os.path.basename(f) for f in xml_filenames])
    return r


def incr(d, value):
    if value is not None:
        if not value in d.keys():
            d[value] = 0
        d[value] += 1
    return d


def more_frequent(d):
    r = None
    t = 0
    for k, v in d.items():
        if v > t:
            t = v
            r = k
    return r


def articles_and_issues(doc_files_info_list):
    articles = {}
    issue_labels = {}
    e_issns = {}
    p_issns = {}

    for doc_files_info in doc_files_info_list:
        new_name = doc_files_info.new_name
        xml_filename = doc_files_info.new_xml_filename
        xml, e = xml_utils.load_xml(xml_filename)

        articles[new_name] = Article(xml) if xml is not None else None
        if xml is not None:
            issue_labels = incr(issue_labels, articles[new_name].issue_label)
            p_issns = incr(p_issns, articles[new_name].print_issn)
            e_issns = incr(e_issns, articles[new_name].e_issn)

    issue_label = more_frequent(issue_labels)
    p_issn = more_frequent(p_issns)
    e_issn = more_frequent(e_issns)
    return (articles, (issue_label, p_issn, e_issn))


def package_validations_report(articles, doc_files_info_list, dtd_files, validate_order, create_toc_report):
    toc_stats_and_report = validate_toc(articles, validate_order)
    articles_stats, articles_reports, articles_sheets = validate_package(articles, doc_files_info_list, dtd_files, validate_order, not create_toc_report)
    texts = format_validation_report(articles_stats, articles_reports, articles_sheets, toc_stats_and_report, create_toc_report)
    return join_reports(texts, './log_xpm.txt')


def join_reports(texts, logfilename):
    r = ''
    for t in texts:
        try:
            r += t
        except Exception as e:
            print(e)
            if 'position' in str(e):
                e = str(e)
                p = e[e.find('position ')+len('position '):]
                print(p)
                p = p[0:p.find(': ')]
                print('.' + p + '.')
                if p.isdigit():
                    try:
                        p = int(p)
                        print(t[0:p])
                        print(t[p:])
                        open(logfilename, 'a+').write(p + '\n')
                        open(logfilename, 'a+').write(t + '\n')
                        open(logfilename, 'a+').write(t[0:p] + '\n')
                        open(logfilename, 'a+').write(t[p:] + '\n')
                    except Exception as e2:
                        print(e2)
    return r


def validate_toc(articles, validate_order):
    return article_reports.toc_report_data(articles, validate_order)


def format_toc_report(toc_stats_and_report):
    text = ''
    if toc_stats_and_report is not None:
        toc_f, toc_e, toc_w, toc_report = toc_stats_and_report
        if toc_f + toc_e + toc_w > 0:
            text = html_report.tag('h2', 'Table of contents Report')
            text += html_report.collapsible_block('toc', 'table of contents validations ' + display_statistics_inline(toc_f, toc_e, toc_w), toc_report)
    return text


def validate_package(articles, doc_files_info_list, dtd_files, validate_order, display_sheets):
    articles_stats = {}
    articles_reports = {}
    articles_sheets = {}

    for doc_files_info in doc_files_info_list:
        new_name = doc_files_info.new_name
        xml_filename = doc_files_info.new_xml_filename

        xml_f, xml_e, xml_w = validate_article_xml(new_name, xml_filename, dtd_files, doc_files_info.dtd_report_filename, doc_files_info.style_report_filename, doc_files_info.ctrl_filename, doc_files_info.err_filename)

        data_f, data_e, data_w, sheet_data = validate_article_data(articles[new_name], new_name, os.path.dirname(xml_filename), doc_files_info.data_report_filename, validate_order, display_sheets)

        articles_stats[new_name] = ((xml_f, xml_e, xml_w), (data_f, data_e, data_w))
        articles_reports[new_name] = (doc_files_info.err_filename, doc_files_info.style_report_filename, doc_files_info.data_report_filename)
        articles_sheets[new_name] = (sheet_data.authors_sheet_data(new_name), sheet_data.sources_sheet_data(new_name))

    return (articles_stats, articles_reports, articles_sheets)


def format_validation_report(articles_stats, articles_reports, articles_sheets, toc_stats_and_report, create_toc_report):
    n = '/' + str(len(articles_reports))
    authors_h = None
    authors_w = None
    sources_h = None
    sources_w = None

    toc_authors_sheet_data = []
    toc_sources_sheet_data = []
    toc_f, toc_e, toc_w, toc_report = toc_stats_and_report

    toc_text = ''
    if create_toc_report:
        toc_text = format_toc_report(toc_stats_and_report)

    if toc_f == 0:
        index = 0
        validations_text = html_report.tag('h2', 'XML Validations')
        for new_name in sorted(articles_reports.keys()):
            index += 1
            item_label = str(index) + n + ' - ' + new_name
            print(item_label)
            validations_text += html_report.tag('h4', item_label)
            xml_f, xml_e, xml_w = articles_stats[new_name][0]
            data_f, data_e, data_w = articles_stats[new_name][1]

            rep1, rep2, rep3 = articles_reports[new_name]

            t = []
            v = []
            content = article_validations_text(rep1)
            if len(content) > 0:
                t.append(os.path.basename(rep1))
                v.append(content)
            content = article_validations_text(rep2)
            if len(content) > 0:
                t.append(os.path.basename(rep2))
                v.append(content)

            content = ''.join(v)
            if xml_f + xml_e + xml_w > 0:
                s = display_statistics_inline(xml_f, xml_e, xml_w)
                validations_text += html_report.collapsible_block('xmlrep' + str(index), '[' + s + ']' + ' and '.join(t), content)

            if data_f + data_e + data_w > 0:
                s = display_statistics_inline(data_f, data_e, data_w)
                validations_text += html_report.collapsible_block('datarep' + str(index), '[' + s + ']' + os.path.basename(rep3), article_validations_text(rep3))

            if create_toc_report:
                authors_h, authors_w, authors_data = articles_sheets[new_name][0]
                toc_authors_sheet_data += authors_data
                sources_h, sources_w, sources_data = articles_sheets[new_name][1]
                toc_sources_sheet_data += sources_data

    lists_text = ''
    if create_toc_report:

        lists_text = html_report.tag('h2', 'Authors and Sources Lists')
        authors = html_report.sheet((authors_h, authors_w, toc_authors_sheet_data))
        lists_text += html_report.collapsible_block('authors', 'Authors in the package', authors)

        sources = html_report.sheet((sources_h, sources_w, toc_sources_sheet_data))
        lists_text += html_report.collapsible_block('sources', 'Sources in the package', sources)

    return [toc_text, validations_text, lists_text]


def display_statistics_inline(f, e, w):
    return ' | '.join([k + ': ' + v for k, v in [('fatal errors', str(f)), ('errors', str(e)), ('warnings', str(w))]])


def processing_result_location(result_path):
    return 'Result of the processing: ' + html_report.link('file:///' + os.path.dirname(result_path), os.path.dirname(result_path))


def save_report(filename, title, content):
    html_report.title = title
    html_report.body = content
    html_report.save(filename)
    print('\n\nReport:\n ' + filename)


def display_report(report_filename):
    try:
        os.system('python -mwebbrowser file:///' + report_filename.replace('//', '/'))
    except:
        pass
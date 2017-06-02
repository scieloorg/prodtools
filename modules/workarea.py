# coding=utf-8

import os
import shutil

from . import fs_utils
from . import img_utils


class Workarea(object):

    def __init__(self, filename, output_path=None):
        self.filename = filename
        self.path = os.path.dirname(filename)
        self.basename = os.path.basename(filename)
        self.name, self.ext = os.path.splitext(self.basename)
        self.new_name = self.name
        xml_generation_path = None
        if filename.endswith('.sgm.xml'):
            xml_generation_path = self.path
            output_path = os.path.dirname(os.path.dirname(self.path))

        self.output_path = output_path
        self.outputs = OutputFiles(self.name, self.reports_path, xml_generation_path)

        for p in [self.output_path, self.reports_path, self.scielo_package_path, self.pmc_package_path]:
            if not os.path.isdir(p):
                os.makedirs(p)

    @property
    def reports_path(self):
        return self.output_path + '/errors'

    @property
    def scielo_package_path(self):
        return self.output_path + '/scielo_package'

    @property
    def pmc_package_path(self):
        return self.output_path+'/pmc_package'


class PackageFiles(object):

    def __init__(self, filename):
        self.filename = filename
        self.path = os.path.dirname(filename)
        self.basename = os.path.basename(filename)
        self.name, self.ext = os.path.splitext(self.basename)
        self.SUFFIXES = ['t', 'f', 'e', 'img', 'image']
        self.SUFFIXES.extend(['-'+s for s in self.SUFFIXES])
        self.SUFFIXES.extend(['-', '.'])

    def add_extension(self, new_href):
        if '.' not in new_href:
            ext = self.files_by_name_except_xml.get(new_href)
            if len(ext) > 1:
                ext = [e for e in extensions if '.tif' in e or '.eps' in e] + extensions
            if len(ext) > 0:
                new_href += ext[0]
        return new_href

    def all_files(self):
        r = []
        for suffix in self.SUFFIXES:
            r += [item for item in os.listdir(self.path) if item.startswith(self.name + suffix)]
        if self.basename.startswith('a') and self.basename[3:4] == 'v':
            prefix = self.basename[:3]
            r += [item for item in os.listdir(self.path) if item.startswith(prefix)]
        r = list(set(r))
        r = [item for item in r if not item.endswith('incorrect.xml') and not item.endswith('.sgm.xml')]
        return sorted(r)

    @property
    def allfiles(self):
        r = []
        for suffix in self.SUFFIXES:
            r += [item for item in os.listdir(self.path) if item.startswith(self.name + suffix)]
        if self.basename.startswith('a') and self.basename[3:4] == 'v':
            prefix = self.basename[:3]
            r += [item for item in os.listdir(self.path) if item.startswith(prefix)]
        r = list(set(r))
        r = [item for item in r if not item.endswith('incorrect.xml') and not item.endswith('.sgm.xml')]
        return sorted(r)

    @property
    def files_except_xml(self):
        return [f for f in self.allfiles if f != self.basename]

    @property
    def files_by_name_except_xml(self):
        files = {}
        for f in self.files_except_xml:
            name, ext = os.path.splitext(f)
            if name not in files.keys():
                files[name] = []
            files[name].append(ext)
        return files

    def clean(self):
        for f in self.files_except_xml:
            fs_utils.delete_file_or_folder(self.path + '/' + f)

    @property
    def splitext(self):
        return [os.path.splitext(f) for f in self.files_by_name_except_xml]

    @property
    def png_items(self):
        return [name+ext for name, ext in self.splitext if ext in ['.png']]

    @property
    def jpg_items(self):
        return [name+ext for name, ext in self.splitext if ext in ['.jpg', '.jpeg']]

    @property
    def tiff_items(self):
        return [name+ext for name, ext in self.splitext if ext in ['.tif', '.tiff']]

    @property
    def png_names(self):
        return [name for name, ext in self.splitext if ext in ['.png']]

    @property
    def jpg_names(self):
        return [name for name, ext in self.splitext if ext in ['.jpg', '.jpeg']]

    @property
    def tiff_names(self):
        return [name for name, ext in self.splitext if ext in ['.tif', '.tiff']]

    def convert_images(self):
        for item in self.tiff_names:
            if not item in self.jpg_names and not item in self.png_names:
                source_fname = item + '.tif'
                if not source_fname in self.files_except_xml:
                    source_fname = item + '.tiff'
                img_utils.hdimg_to_jpg(self.path + '/' + source_fname, self.path + '/' + item + '.jpg')
                if item + '.jpg' not in self.allfiles:
                    print('!'*30)
                    print('workarea.files problem')

    def zip(self, dest_path=None):
        if dest_path is None:
            dest_path = os.path.dirname(self.path)
        filename = dest_path + '/' + self.name + '.zip'
        fs_utils.zip(filename, [self.path + '/' + f for f in self.allfiles])
        return filename

    def copy(self, dest_path):
        if dest_path is not None:
            if not os.path.isdir(dest_path):
                os.makedirs(dest_path)
            for f in self.files_except_xml:
                shutil.copyfile(self.path + '/' + f, dest_path + '/' + f)


class PackageFolder(object):

    def __init__(self, path):
        self.path = path
        self.xml_names = [f[:f.rfind('.')] for f in os.listdir(self.path) if f.endswith('.xml') and not f.endswith('.sgm.xml')]
        self.xml_list = [self.path + '/' + f for f in os.listdir(self.path) if f.endswith('.xml') and not f.endswith('.sgm.xml')]

    @property
    def packages(self):
        items = []
        for item in self.xml_list:
            items.append(PackageFiles(item))
        return items

    @property
    def package_files(self):
        items = []
        for pkg in self.packages:
            items.extend(pkg.allfiles)
        return items

    @property
    def orphans(self):
        items = []
        for f in os.listdir(self.path):
            if f not in self.package_files:
                items.append(f)
        return items

    def zip(self, dest_path=None):
        if dest_path is None:
            dest_path = os.path.dirname(self.path)
        filename = dest_path + '/' + os.path.basename(self.path) + '.zip'
        fs_utils.zip(filename, [self.path + '/' + f for f in self.package_files])
        return filename


class OutputFiles(object):

    def __init__(self, xml_name, report_path, wrk_path):
        self.xml_name = xml_name
        self.report_path = report_path
        self.wrk_path = wrk_path

        #self.related_files = []
        #self.xml_filename = xml_filename
        #self.new_xml_filename = self.xml_filename
        #self.xml_path = os.path.dirname(xml_filename)
        #self.xml_name = basename.replace('.xml', '')
        #self.new_name = self.xml_name

    @property
    def report_path(self):
        return self._report_path

    @report_path.setter
    def report_path(self, _report_path):
        if not os.path.isdir(_report_path):
            os.makedirs(_report_path)
        self._report_path = _report_path

    @property
    def ctrl_filename(self):
        if self.wrk_path is not None:
            if not os.path.isdir(self.wrk_path):
                os.path.makedirs(self.wrk_path)
            return self.wrk_path + '/' + self.xml_name + '.ctrl.txt'

    @property
    def style_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.rep.html'

    @property
    def dtd_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.dtd.txt'

    @property
    def pmc_dtd_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.pmc.dtd.txt'

    @property
    def pmc_style_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.pmc.rep.html'

    @property
    def err_filename(self):
        return self.report_path + '/' + self.xml_name + '.err.txt'

    @property
    def err_filename_html(self):
        return self.report_path + '/' + self.xml_name + '.err.html'

    @property
    def data_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.contents.html'

    @property
    def images_report_filename(self):
        return self.report_path + '/' + self.xml_name + '.images.html'

    @property
    def xml_structure_validations_filename(self):
        return self.report_path + '/xmlstr-' + self.xml_name

    @property
    def xml_content_validations_filename(self):
        return self.report_path + '/xmlcon-' + self.xml_name

    @property
    def journal_validations_filename(self):
        return self.report_path + '/journal-' + self.xml_name

    @property
    def issue_validations_filename(self):
        return self.report_path + '/issue-' + self.xml_name

    def clean(self):
        for f in [self.err_filename, self.dtd_report_filename, self.style_report_filename, self.pmc_dtd_report_filename, self.pmc_style_report_filename, self.ctrl_filename]:
            fs_utils.delete_file_or_folder(f)

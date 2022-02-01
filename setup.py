#!/usr/bin/env python
# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import os
from pathlib import Path
import platform
import sysconfig
from distutils.log import info, warn
from distutils.spawn import find_executable

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

from numpy.distutils.misc_util import get_numpy_include_dirs

from Cython.Build import cythonize

def env_path(name):
    P = os.environ.get(name)
    if P:
        return P.split(os.pathsep)
    else:
        return []

include_dirs = env_path('AACLIENT_INCLUDE_DIRS')
include_dirs += get_numpy_include_dirs()
include_dirs.append('aaclient') # aaclient/pb.h

library_dirs = env_path('AACLIENT_LIB_DIRS')

if platform.system()=='Windows':
    protobuf_lite='libprotobuf-lite' # yup. really...
else:
    protobuf_lite='protobuf-lite'


class BuildProtoC(build_ext):
    def initialize_options(self):
        build_ext.initialize_options(self)
        self.protoc = 'protoc'
        self.strip = 'strip'

    def finalize_options(self):
        build_ext.finalize_options(self)

        self.__path=os.pathsep.join([
            os.environ['PATH'],
            os.environ.get('AACLIENT_PATH', ''),
        ])

        self.protoc = find_executable(self.protoc, path=self.__path)
        self.strip = find_executable(self.strip, path=self.__path)

        self.protoout = Path(self.build_temp)
        self.mkpath(str(self.protoout))
        self.include_dirs.append(self.protoout)

    def build_extension(self, ext):
        new_srcs, orig_srcs = [], ext.sources
        for src in orig_srcs:
            base, ftype = os.path.splitext(src) # "EPICSEvent.proto" -> ("EPICSEvent", ".proto")
            if ftype=='.proto':
                proto = src

                # expected protoc output file name
                tmp = self.protoout / (base + '.pb.cc') # "build/temp.*/EPICSEvent.pb.cc"

                # final source name
                src = tmp.with_suffix('.cpp') # "build/temp.*/EPICSEvent.pb.cpp"

                info("GEN protoc {!r} -> {!r}".format(proto, src))

                if not self.protoc:
                    raise RuntimeError("Failed to find protoc executable in %s"%self.__path)

                self.spawn([self.protoc, '--cpp_out='+str(self.protoout), proto])

                if not src.exists() or src.read_bytes()!=tmp.read_bytes():
                    info("UPDATED {!r}".format(src))
                    self.copy_file(tmp, src)
                else:
                    info("UNCHANGED {!r}".format(src))

            new_srcs.append(str(src))

        ext.sources = new_srcs
        build_ext.build_extension(self, ext)
        ext.sources = orig_srcs

        if platform.system()=='Linux' and not sysconfig.get_config_var('Py_DEBUG') and self.strip:
            self.spawn([self.strip, '--strip-debug', self.get_ext_fullpath(ext.name)])

    def run(self):
        build_ext.run(self)
        if platform.system()=='Windows':
            # Copy in protobuf-lite dll
            dll=protobuf_lite+'.dll'
            dest=os.path.join(self.build_lib, 'aaclient', dll)
            info('Searching for %r in %r', dll, self.__path)
            for dname in self.__path.split(os.pathsep):
                if not dname or not os.path.isdir(dname):
                    continue
                cand = os.path.join(dname, dll)
                if os.path.isfile(cand):
                    info('Copying %r -> %r', cand, dest)
                    self.copy_file(cand, dest)
                    break
            else:
                warn("Did not find %r", dll)


BuildProtoC.user_options = build_ext.user_options + [
    ('protoc=', 'P', "protobuf compiler"),
]

setup(
    ext_modules=cythonize([
        Extension(name='aaclient._ext',
                  include_dirs = include_dirs,
                  library_dirs = library_dirs,
                  sources=['aaclient/ext.pyx', 'aaclient/EPICSEvent.proto'],
                  libraries=[protobuf_lite],
                  extra_compile_args=['-std=c++11'],
        ),
    ]),

    cmdclass = {
        'build_ext':BuildProtoC,
    },
)

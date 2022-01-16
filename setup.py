#!/usr/bin/env python
# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import os
from pathlib import Path
from shutil import copyfile

from distutils.log import info
from distutils.spawn import find_executable

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

from Cython.Build import cythonize

class BuildProtoC(build_ext):
    def initialize_options(self):
        build_ext.initialize_options(self)
        self.protoc = 'protoc'

    def finalize_options(self):
        build_ext.finalize_options(self)

        if self.protoc and not os.path.isfile(self.protoc):
            self.protoc = find_executable(self.protoc)

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

                self.spawn([self.protoc, '--cpp_out='+str(self.protoout), proto])

                if not src.exists() or src.read_bytes()!=tmp.read_bytes():
                    info("UPDATED {!r}".format(src))
                    copyfile(tmp, src)
                else:
                    info("UNCHANGED {!r}".format(src))

            new_srcs.append(str(src))

        ext.sources = new_srcs
        build_ext.build_extension(self, ext)
        ext.sources = orig_srcs


BuildProtoC.user_options = build_ext.user_options + [
    ('protoc=', 'P', "protobuf compiler"),
]

setup(
    ext_modules=cythonize([
        Extension(name='aaclient._ext',
                  sources=['aaclient/ext.pyx', 'aaclient/EPICSEvent.proto'],
                  libraries=['protobuf-lite'],
                  define_macros=[('NPY_NO_DEPRECATED_API','NPY_1_7_API_VERSION')],
        ),
    ]),

    cmdclass = {
        'build_ext':BuildProtoC,
    },
)

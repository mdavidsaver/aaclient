# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

# bundled string.pxd is missing many except+
#from libcpp.string cimport string

cdef extern from "<string>" namespace "std" nogil:
    cdef cppclass string:
        string() except +

        const char* c_str()
        const char* data()
        size_t size() const
        bint empty() const

        void reserve(size_t) except+
        void clear()

        string& append(const char *) except+
        void push_back(char c) except+

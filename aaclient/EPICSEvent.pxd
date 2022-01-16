# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

from libc.stdint cimport int32_t, uint32_t
from libcpp cimport bool
from .libcppx cimport string

cdef extern from * namespace "" nogil:
    cdef cppclass MessageLite:
        bool ParseFromString(const string& data) except+
        bool ParseFromArray(const void* data, int size) except+
        bool SerializeToString(string* output) except+

cdef extern from "aaclient/EPICSEvent.pb.h" namespace "EPICS" nogil:
    ctypedef enum PayloadType:
        SCALAR_STRING
        SCALAR_SHORT 
        SCALAR_FLOAT
        SCALAR_ENUM
        SCALAR_BYTE
        SCALAR_INT
        SCALAR_DOUBLE
        WAVEFORM_STRING
        WAVEFORM_SHORT
        WAVEFORM_FLOAT
        WAVEFORM_ENUM
        WAVEFORM_BYTE
        WAVEFORM_INT
        WAVEFORM_DOUBLE
        V4_GENERIC_BYTES

    cdef cppclass FieldValue(MessageLite):
        const string& name() const
        const string& val() const

        void set_name(const string&) except+
        void set_val(const string&) except+

    cdef cppclass PayloadInfo(MessageLite):
        PayloadInfo()
        PayloadType type() const
        const string& pvname() const
        int32_t year() const
        int32_t elementcount() const
        int headers_size() const
        const FieldValue& headers(int) const

        void set_type(PayloadType)
        void set_pvname(const string&) except+
        void set_year(int32_t)
        void set_elementcount(int32_t)
        FieldValue* add_headers() except+

    # not a real base class
    # avoid repeating definitions for accessor methods common to all
    cdef cppclass FakeBase(MessageLite):
        uint32_t secondsintoyear() const
        uint32_t nano() const
        int32_t severity() const
        int32_t status() const
        uint32_t repeatcount() const
        int fieldvalues_size() const
        const FieldValue& fieldvalues(int) const

        void set_secondsintoyear(uint32_t)
        void set_nano(uint32_t)
        void set_severity(int32_t)
        void set_status(int32_t)
        void set_repeatcound(int32_t)
        FieldValue* add_fieldvalues() except+

    cdef cppclass ScalarString(FakeBase):
        const string val() const
        void set_val(const string&) except+

    cdef cppclass ScalarByte(FakeBase):
        const string val() const
        void set_val(const string&) except+

    cdef cppclass ScalarShort(FakeBase):
        int32_t val() const
        void set_val(int32_t)

    cdef cppclass ScalarInt(FakeBase):
        int32_t val() const
        void set_val(int32_t)

    cdef cppclass ScalarEnum(FakeBase):
        int32_t val() const
        void set_val(int32_t)

    cdef cppclass ScalarFloat(FakeBase):
        float val() const
        void set_val(float)

    cdef cppclass ScalarDouble(FakeBase):
        double val() const
        void set_val(double)

    cdef cppclass VectorString(FakeBase):
        pass

    cdef cppclass VectorChar(FakeBase):
        const string val() const
        void set_val(const string&) except+

    cdef cppclass VectorShort(FakeBase):
        int val_size() const
        int32_t val(int) const
        void add_val(int32_t) except+

    cdef cppclass VectorInt(FakeBase):
        int val_size() const
        int32_t val(int) const
        void add_val(int32_t) except+

    cdef cppclass VectorEnum(FakeBase):
        int val_size() const
        int32_t val(int) const
        void add_val(int32_t) except+

    cdef cppclass VectorFloat(FakeBase):
        int val_size() const
        float val(int) const
        void add_val(float) except+

    cdef cppclass VectorDouble(FakeBase):
        int val_size() const
        double val(int) const
        void add_val(double) except+

    cdef cppclass V4GenericBytes(FakeBase):
        const string val() const
        uint32_t usertag() const
        void set_val(const string&) except+
        void set_usertag(uint32_t)

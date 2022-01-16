# distutils: language = c++
#cython: language_level=3

# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

cimport cython
from libc.stdint cimport int16_t, uint32_t, int32_t
from libcpp.vector cimport vector
from libcpp.memory cimport unique_ptr

import numpy as np
cimport numpy as np

from .libcppx cimport string
from .EPICSEvent cimport *

from . import dtype

cdef extern from "pb.h" nogil:
    # must match .dtype.dbr_time
    struct dbr_time:
        uint32_t sec
        uint32_t ns
        uint32_t severity
        uint32_t status

    void encode_sample[PB](string&, const void*, size_t, const dbr_time&, const char*) except+

    cppclass Decoder:
        PayloadType ptype
        size_t maxelems
        int32_t sectoyear

        @staticmethod
        void prepare(unique_ptr[Decoder]& out, PayloadType pinfo, int32_t sectoyear) except+

        size_t process(const string&) except+
        size_t nsamples() const
        void copy_out(void* raw, dbr_time* meta) except+

### AA line <-> PB blob escaping

cdef Py_ssize_t splitpb(const char* inp, size_t inlen, string& out) nogil except -1:
    cdef:
        size_t i
        bint escape = 0
        char c

    out.clear()
    out.reserve(inlen)

    for i in range(inlen):
        c = inp[i]
        if escape:
            escape = 0
            if c==b'\x01':
                c = b'\x1b'
            elif c==b'\x02':
                c = b'\n'
            elif c==b'\x03':
                c = b'\r'
            else:
                return -2 # unknown/invalid escape

        elif c==b'\x1b':
            escape = 1
            continue

        elif c==b'\n': # end of sample
            return i+1

        out.push_back(c)

    return 0 # incomplete sample

def split(bytes input):
    """split(bytes) -> [bytes], bytes
    Take in an AA escaped byte string.
    Return a list of PB encoded blobs, and any trailing input bytes of an incomplete blob
    """
    cdef:
        Py_ssize_t consumed = 0
        const char* orig = input
        const char* inp = orig
        size_t inlen = len(input)
        string temp
        list ret = []

    while inlen:
        consumed = splitpb(inp, inlen, temp)
        if consumed==0:
            break
        elif consumed < 0:
            raise ValueError(f"{consumed} : {input!r}")
        inp += consumed
        inlen -= consumed
        ret.append(temp)

    return ret, input[(inp-orig):]

cdef int escapexx(const char* inp, size_t inlen, string& out) nogil except -1:
    cdef:
        char c

    out.clear()
    out.reserve(inlen)

    for i in range(inlen):
        c = inp[i]
        if c==b'\x1b':
            out.append(b"\x1b\x01")
        elif c==b'\n':
            out.append(b"\x1b\x02")
        elif c==b'\r':
            out.append(b"\x1b\x03")
        else:
            out.push_back(c)

    return 0

def join(samps):
    cdef:
        const char* inp
        size_t inlen
        string out

    ret = []

    for s in samps:
        inp = s
        inlen = len(s)
        if 0!=escapexx(inp, inlen, out):
            raise ValueError(s)
        out.push_back(b'\n')
        ret.append(out)

    return b''.join(ret)

### PB Decoding

def encode_PayloadInfo(dict inp):
    cdef:
        int ret
        string out
        PayloadInfo info

    info.set_type(inp['type'])
    info.set_pvname(inp['pvname'])
    info.set_year(inp['year'])
    info.set_elementcount(inp['elementCount'])

    for N,V in inp['headers']:
        FV = info.add_headers()
        FV.set_name(N)
        FV.set_val(V)

    if not info.SerializeToString(&out):
        raise ValueError("PB Print")

    return out

def decode_PayloadInfo(bytes input) -> dict:
    """decode a single line as a PayloadInfo
    """
    cdef:
        int ret
        const char* inp = input
        size_t inlen = len(input)
        PayloadInfo out

    if not out.ParseFromArray(inp, inlen):
        raise ValueError(f"PB Parse : {input!r}")

    return {
        'type': <int>out.type(),
        'pvname': out.pvname(),
        'year': out.year(),
        'elementCount': out.elementcount(),
        'headers': [(out.headers(i).name(), out.headers(i).val()) for i in range(out.headers_size())]
    }

def encode_samples(ptype, list samps):
    """encode_samples([dict]) -> [bytes]
    """
    cdef:
        PayloadType pt = <PayloadType><int>ptype
        string raw
        dbr_time meta
        const char* cnxlostepsecs
        string vstr
        int16_t i16
        int32_t i32
        float f32
        double f64
        vector[string] astr
        vector[int16_t] ai16
        vector[int32_t] ai32
        vector[float] af32
        vector[double] af64

    ret = [None]*len(samps)

    for i,samp in enumerate(samps):
        meta.sec = samp['sec'] # caller should already subtrace sectoyear
        meta.ns = samp['ns']
        meta.severity = samp['sevr']
        meta.status = samp['status']
        if 'cnxlostepsecs' in samp:
            cnxlostepsecs = samp['cnxlostepsecs']
        else:
            cnxlostepsecs = NULL

        V = samp['val']

        if pt==SCALAR_STRING or pt==SCALAR_BYTE or pt==V4_GENERIC_BYTES:
            vstr = V
            if pt==SCALAR_STRING:
                encode_sample[ScalarString](raw, &vstr, 1, meta, cnxlostepsecs)
            elif pt==SCALAR_BYTE:
                encode_sample[ScalarByte](raw, &vstr, 1, meta, cnxlostepsecs)
            elif pt==V4_GENERIC_BYTES:
                encode_sample[V4GenericBytes](raw, &vstr, 1, meta, cnxlostepsecs)

        elif pt==SCALAR_SHORT or pt==SCALAR_ENUM:
            i16 = V
            if pt==SCALAR_ENUM:
                encode_sample[ScalarShort](raw, &i16, 1, meta, cnxlostepsecs)
            elif pt==SCALAR_ENUM:
                encode_sample[ScalarEnum](raw, &i16, 1, meta, cnxlostepsecs)

        elif pt==SCALAR_INT:
            i32 = V
            encode_sample[ScalarInt](raw, &i32, 1, meta, cnxlostepsecs)

        elif pt==SCALAR_FLOAT:
            f32 = V
            encode_sample[ScalarFloat](raw, &f32, 1, meta, cnxlostepsecs)

        elif pt==SCALAR_DOUBLE:
            f64 = V
            encode_sample[ScalarDouble](raw, &f64, 1, meta, cnxlostepsecs)

        elif pt==WAVEFORM_STRING:
            astr.resize(len(V))
            for i,v in enumerate(V):
                astr[i] = v
            encode_sample[VectorString](raw, astr.data(), astr.size(), meta, cnxlostepsecs)

        elif pt==WAVEFORM_SHORT or pt==WAVEFORM_ENUM:
            ai16.resize(len(V))
            for i,v in enumerate(V):
                ai16[i] = v
            if pt==WAVEFORM_SHORT:
                encode_sample[VectorShort](raw, ai16.data(), ai16.size(), meta, cnxlostepsecs)
            elif pt==WAVEFORM_ENUM:
                encode_sample[VectorEnum](raw, ai16.data(), ai16.size(), meta, cnxlostepsecs)

        elif pt==WAVEFORM_INT:
            ai32.resize(len(V))
            for i,v in enumerate(V):
                ai32[i] = v
            encode_sample[VectorInt](raw, ai32.data(), ai32.size(), meta, cnxlostepsecs)

        elif pt==WAVEFORM_FLOAT:
            af32.resize(len(V))
            for i,v in enumerate(V):
                af32[i] = v
            encode_sample[VectorFloat](raw, af32.data(), af32.size(), meta, cnxlostepsecs)

        elif pt==WAVEFORM_DOUBLE:
            af64.resize(len(V))
            for i,v in enumerate(V):
                af64[i] = v
            encode_sample[VectorDouble](raw, af64.data(), af64.size(), meta, cnxlostepsecs)

        else:
            raise NotImplementedError(ptype)

        ret[i] = raw

    return ret

from calendar import timegm # libc provides no portable alternative

@cython.auto_pickle(False)
cdef class StreamDecoder:
    """Decodes an AA byte stream of escaped PB blobs
    """
    cdef:
        # 0 - Waiting for PayloadInfo
        # 1 - Waiting for sample
        uint32_t pstate
        size_t threshold
        unique_ptr[Decoder] dec
        # scratch buffer for unescaping.  Presistent to avoid some realloc
        string unesc
        # (partial/remaining) unescaped input
        bytes buf
        # last=True has been passed.  self.buf is complete
        bint seenlast
        # whether to silently merge when next PayloadType has same type and year
        bint consolidate
    cdef public:
        list output

    def __cinit__(self, threshold, consolidate=False):
        self.threshold = threshold
        self.consolidate = consolidate
        self.pstate = 0
        self.seenlast = False
        self.buf = None
        self.output = []

    def process(self, bytes input = None, bint last = False):
        """process(bytes input, bool last) -> bool
        Process further, perhaps last, input bytes.

        Take in an AA escaped byte stream and yield an triple of
        values, metas, and any remaining bytes.

        Practically, this strips off and decodes a PayloadInfo, and any samples
        which follow until an empty line is encountered
        """
        cdef:
            const char* orig = NULL
            const char* inp = NULL
            size_t remaining = 0
            Py_ssize_t consumed = 0
            int32_t sectoyear
            np.ndarray V = None
            np.ndarray M = None
            bint fin = last
            bint flush = fin
            PayloadInfo curinfo

        if self.seenlast:
            raise RuntimeError("Already last=True")
        self.seenlast = fin

        if self.buf is None:
            self.buf = input

        elif input is not None:
            self.buf = self.buf + input

        if self.buf is not None:
            orig = self.buf
            inp = orig
            remaining = len(self.buf)

        with nogil:
            while remaining:
                consumed = splitpb(inp, remaining, self.unesc)
                if consumed<0 or <size_t>consumed>remaining:
                    raise ValueError(f"{inp-orig} {consumed} {remaining}")

                inp += consumed
                remaining -= consumed

                if consumed==0: # need more bytes before further progress is possible...
                    break

                elif self.pstate==0: # next line is PayloadInfo

                    if not curinfo.ParseFromString(self.unesc):
                        raise ValueError(f"PayloadInfo Parse : {self.unesc!r}")

                    with gil:
                        sectoyear = timegm((curinfo.year(), 1, 1, 0, 0, 0, 0, 0, 0))

                        if not self.dec or not self.consolidate \
                            or self.dec.get().ptype!=curinfo.type() \
                            or self.dec.get().sectoyear!=sectoyear:
                            # first, or type/year change
                            self.__finish_output()
                            Decoder.prepare(self.dec, curinfo.type(), sectoyear)
                        # else: implicit concat when type/year doesn't change

                    self.pstate = 1

                elif self.unesc.empty(): # blank line ends current list of samples
                    self.pstate = 0

                else: # decode a sample
                    if self.dec.get().process(self.unesc) >= self.threshold:
                        with gil:
                            self.__finish_output()

        if self.seenlast and remaining and not consumed:
            raise ValueError(f"Truncated sample in state {self.state}")

        if remaining:
            self.buf = self.buf[(inp-orig):]
        else:
            self.buf = None

        if self.seenlast and remaining and inp==orig:
            # no forward progress with entire input.  we're stuck
            raise ValueError(f"Truncated or corrupt trailing sample {self.buf!r}")

        if self.dec and ((self.seenlast and self.buf is None) or self.dec.get().nsamples()>=self.threshold):
            self.__finish_output()

        return self.buf is None

    def __finish_output(self):
        # transfer samples from self.dec to self.out
        if not self.dec:
            return

        nsamples = self.dec.get().nsamples()

        if not nsamples:
            return

        M = np.zeros(nsamples,
                     dtype=dtype.dbr_time)
        V = np.zeros((nsamples, self.dec.get().maxelems),
                     dtype=dtype.pt2dt[self.dec.get().ptype])

        if not np.PyArray_CHKFLAGS(V, np.NPY_ARRAY_C_CONTIGUOUS) or \
            not np.PyArray_CHKFLAGS(M, np.NPY_ARRAY_C_CONTIGUOUS):
            raise ValueError("Failed to allocate contiguous.  logic error?")

        varr = np.PyArray_GETPTR2(V,0,0)
        marr = <dbr_time*>np.PyArray_GETPTR1(M,0)

        with nogil:
            self.dec.get().copy_out(varr, marr)

        self.output.append((V, M))

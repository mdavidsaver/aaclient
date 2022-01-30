/*
 * Copyright 2022 Michael Davidsaver
 * SPDX-License-Identifier: BSD
 * See LICENSE file
 */
#ifndef PB_H
#define PB_H

#include <stdexcept>
#include <type_traits>
#include <memory>
#include <sstream>

#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include <aaclient/EPICSEvent.pb.h>

struct dbr_time {
  uint32_t sec;
  uint32_t ns;
  uint32_t severity;
  uint32_t status;
};

namespace {
using namespace EPICS;

template<typename PB>
struct PBAttr;

#define PBATTR(PB, PT, VAL, ARR) \
template<> \
struct PBAttr<PB> { \
    static constexpr EPICS::PayloadType ptype = PT; \
    typedef VAL type; \
    static constexpr bool repeated = ARR; \
}
PBATTR(ScalarString, SCALAR_STRING, std::string, false);
PBATTR(ScalarByte, SCALAR_BYTE, std::string, false);
PBATTR(ScalarShort, SCALAR_SHORT, int16_t, false);
PBATTR(ScalarEnum, SCALAR_ENUM, int16_t, false);
PBATTR(ScalarInt, SCALAR_INT, int32_t, false);
PBATTR(ScalarFloat, SCALAR_FLOAT, float, false);
PBATTR(ScalarDouble, SCALAR_DOUBLE, double, false);
PBATTR(VectorString, WAVEFORM_STRING, std::string, true);
PBATTR(VectorChar, WAVEFORM_BYTE, std::string, false);
PBATTR(VectorShort, WAVEFORM_SHORT, int16_t, true);
PBATTR(VectorEnum, WAVEFORM_ENUM, int16_t, true);
PBATTR(VectorInt, WAVEFORM_INT, int32_t, true);
PBATTR(VectorFloat, WAVEFORM_FLOAT, float, true);
PBATTR(VectorDouble, WAVEFORM_DOUBLE, double, true);
PBATTR(V4GenericBytes, V4_GENERIC_BYTES, std::string, false);
#undef PBATTR

template<typename PB>
typename std::enable_if<!PBAttr<PB>::repeated>::type
set_val(PB& pb, const typename PBAttr<PB>::type* v, size_t nv)
{
    pb.set_val(*v);
}

template<typename PB>
typename std::enable_if<PBAttr<PB>::repeated>::type
set_val(PB& pb, const typename PBAttr<PB>::type* v, size_t nv)
{
    auto arr = pb.mutable_val();
    arr->Reserve(nv);
    for(size_t i=0; i<nv; i++) {
        *arr->Add() = v[i];
    }
}

void encode_error() {
    throw std::runtime_error("PB Encode error");
}

template<typename PB>
void encode_sample(std::string&out,
                   const typename PBAttr<PB>::type* v, size_t nv,
                   const dbr_time& meta, const char* cnxlostepsecs)
{
    PB pb;

    pb.set_secondsintoyear(meta.sec);
    pb.set_nano(meta.ns);
    if(meta.severity)
        pb.set_severity(meta.severity);
    if(meta.status)
        pb.set_status(meta.status);
    if(cnxlostepsecs) {
        FieldValue* fv = pb.add_fieldvalues();
        fv->set_name("cnxlostepsecs");
        fv->set_name(cnxlostepsecs);
    }

    set_val(pb, (const typename PBAttr<PB>::type*)v, nv);
    if(!pb.SerializeToString(&out))
        encode_error();
}

template<typename PB>
typename std::enable_if<!PBAttr<PB>::repeated, size_t>::type
val_count(const PB& pb) { return 1u; }

template<typename PB>
typename std::enable_if<PBAttr<PB>::repeated, size_t>::type
val_count(const PB& pb) { return pb.val_size(); }

template<typename V>
typename std::enable_if<std::is_pod<V>::value>::type
val_assign(V v, char *& cur, size_t maxelems)
{
    *reinterpret_cast<V*>(cur) = v;
    cur += sizeof(V)*maxelems;
}

template<typename E>
typename std::enable_if<std::is_pod<E>::value>::type
val_assign(const google::protobuf::RepeatedField<E>& v, char *& cur, size_t maxelems)
{
    cur += sizeof(E)*maxelems;
}

void val_assign(const std::string& v, char *& cur, size_t maxelems)
{
    size_t l = v.size();
    if(l>40)
        l = 40;
    memcpy(cur, v.c_str(), l);
    cur += 40*maxelems;
}

void val_assign(const google::protobuf::RepeatedPtrField<std::string>& v, char *& cur, size_t maxelems)
{
    for(size_t i=0, N=v.size(); i<N; i++) {
        const auto& s = v.Get(i);
        size_t l = s.size();
        if(l>40)
            l = 40;
        memcpy(cur+40*i, s.c_str(), l);
    }
    cur += 40*maxelems;
}


struct Decoder {
    static
    void prepare(std::unique_ptr<Decoder>& out, PayloadType ptype, int32_t sectoyear);

    virtual ~Decoder() {};

    virtual size_t process(const std::string& inp) =0;
    virtual size_t nsamples() const =0;
    virtual void copy_out(void* vals, dbr_time* meta) =0;

    size_t maxelems;
    int32_t sectoyear;
    PayloadType ptype;
};

template<typename PB>
struct DecoderPB : public Decoder {
    std::vector<PB> pbs;

    virtual ~DecoderPB() {}

    virtual size_t process(const std::string& linebuf) override final {
        bool cnxlostepsecs = false;
        uint32_t sec = 0;
        {
            pbs.emplace_back();
            auto& pb = pbs.back();

            if(!pb.ParseFromString(linebuf))
                throw std::runtime_error("Decode error");

            size_t cnt = val_count(pb);

            if(maxelems < cnt)
                maxelems = cnt;


            for(int i=0, N=pb.fieldvalues_size(); i<N; i++) {
                auto fv = pb.fieldvalues(i);
                if(fv.name()=="cnxlostepsecs") {
                    std::istringstream strm(fv.val());

                    if(!(strm>>sec).bad()) {
                        cnxlostepsecs = true;
                        sec -= sectoyear;
                    }
                }
            }
        }

        if(cnxlostepsecs) {
            /* There was a disconnect event before the one just inserted.
             * We will insert a "fake" event w/ alarm to note a possible missed events
             */
            pbs.emplace(pbs.end()-1);
            auto& pb = pbs[pbs.size()-2u];
            pb.set_secondsintoyear(sec);
            pb.set_nano(0);
            pb.set_severity(3904);
        }

        return pbs.size();
    }

    virtual size_t nsamples() const override final {
        return pbs.size();
    }

    // vals expected to be [maxelems][nsamples()]
    // meta expected to be [nsamples()]
    virtual void copy_out(void* raw, dbr_time* meta) override final {
        char* cur = (char*)raw;
        for(const auto& pb : pbs) {
            meta->sec = pb.secondsintoyear() + sectoyear;
            meta->ns = pb.nano();
            meta->severity = pb.severity();
            meta->status = pb.status();
            meta++;
            val_assign(pb.val(), cur, maxelems);
        }
        pbs.clear();
    }
};

void Decoder::prepare(std::unique_ptr<Decoder>& ret, PayloadType ptype, int32_t sectoyear)
{
    switch(ptype) {
#define CASE(PB) case PBAttr<PB>::ptype: ret.reset(new DecoderPB<PB>); break
    CASE(ScalarString);
    CASE(ScalarByte);
    CASE(ScalarShort);
    CASE(ScalarEnum);
    CASE(ScalarInt);
    CASE(ScalarFloat);
    CASE(ScalarDouble);
    CASE(VectorString);
    CASE(VectorChar);
    CASE(VectorShort);
    CASE(VectorEnum);
    CASE(VectorInt);
    CASE(VectorFloat);
    CASE(VectorDouble);
    CASE(V4GenericBytes);
#undef CASE
    }
    ret->maxelems = 0;
    ret->ptype = ptype;
    ret->sectoyear = sectoyear;
}

} // namespace

#endif // PB_H

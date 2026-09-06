// pybind11 binding for the LaVision ReadIMX/ReadIM7 C++ readers.
//
// Replaces the old SWIG-generated `_core` extension. Unlike the SWIG binding,
// this one does not expose the raw BufferType/AttributeList C structs to
// Python: read_file() copies the data into numpy arrays and a plain dict,
// then frees the C buffer/attribute list itself, so callers never have to
// call DestroyBuffer/DestroyAttributeList manually.

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cstring>
#include <stdexcept>

#include "ReadIMX.h"
#include "ReadIM7.h"

namespace py = pybind11;

namespace {

py::dict scale_to_dict(const BufferScaleType& s)
{
    py::dict d;
    d["factor"] = s.factor;
    d["offset"] = s.offset;
    d["description"] = std::string(s.description);
    d["unit"] = std::string(s.unit);
    return d;
}

void dict_to_scale(const py::dict& d, BufferScaleType* s)
{
    SetBufferScale(s,
                   d.contains("factor") ? d["factor"].cast<float>() : 1.0f,
                   d.contains("offset") ? d["offset"].cast<float>() : 0.0f,
                   d.contains("description") ? d["description"].cast<std::string>().c_str() : "",
                   d.contains("unit") ? d["unit"].cast<std::string>().c_str() : "");
}

const char* error_message(int err)
{
    switch (err) {
        case IMREAD_ERR_NO:                       return nullptr;
        case IMREAD_ERR_FILEOPEN:                 return "File not found";
        case IMREAD_ERR_HEADER:                   return "Error in header";
        case IMREAD_ERR_FORMAT:                   return "Error in format";
        case IMREAD_ERR_DATA:                     return "Error while reading data";
        case IMREAD_ERR_MEMORY:                   return "Error out of memory";
        case IMREAD_ERR_ATTRIBUTE_INVALID_TYPE:   return "Invalid attribute type";
        case IMREAD_ERR_ATTRIBUTE_NO_DATA:        return "Missing attribute data";
        default:                                  return "Unknown error while reading file";
    }
}

py::dict read_file(const std::string& filename)
{
    BufferType buff{};
    AttributeList* atts = nullptr;

    int err = ReadIM7(filename.c_str(), &buff, &atts);
    if (err != IMREAD_ERR_NO) {
        if (buff.floatArray || buff.wordArray) DestroyBuffer(&buff);
        if (atts) DestroyAttributeList(&atts);
        throw std::runtime_error(error_message(err));
    }

    int components = buff.image_sub_type > 0 ? GetVectorComponents((BufferFormat_t)buff.image_sub_type) : 1;
    components *= buff.nf;

    py::array array;
    if (buff.isFloat) {
        array = py::array_t<float>({components, buff.ny, buff.nx});
        std::memcpy(array.mutable_data(), buff.floatArray,
                    sizeof(float) * (size_t)components * buff.ny * buff.nx);
    } else {
        array = py::array_t<uint16_t>({components, buff.ny, buff.nx});
        std::memcpy(array.mutable_data(), buff.wordArray,
                    sizeof(uint16_t) * (size_t)components * buff.ny * buff.nx);
    }

    py::object mask = py::none();
    if (buff.bMaskArray) {
        py::array_t<bool> m({buff.nf, buff.ny, buff.nx});
        std::memcpy(m.mutable_data(), buff.bMaskArray,
                    sizeof(bool) * (size_t)buff.nf * buff.ny * buff.nx);
        mask = m;
    }

    // Attribute values are not guaranteed to be valid UTF-8 (e.g. a raw
    // latin-1 micro sign byte), so hand back bytes and let Python decode
    // leniently instead of py::str's strict UTF-8 decode.
    py::dict attributes;
    for (AttributeList* a = atts; a != nullptr; a = a->next) {
        attributes[py::bytes(a->name)] = py::bytes(a->value);
    }

    py::dict out;
    out["nx"] = buff.nx;
    out["ny"] = buff.ny;
    out["nz"] = buff.nz;
    out["nf"] = buff.nf;
    out["vector_grid"] = buff.vectorGrid;
    out["image_sub_type"] = buff.image_sub_type;
    out["is_float"] = (bool)buff.isFloat;
    out["scaleX"] = scale_to_dict(buff.scaleX);
    out["scaleY"] = scale_to_dict(buff.scaleY);
    out["scaleI"] = scale_to_dict(buff.scaleI);
    out["array"] = array;
    out["mask"] = mask;
    out["attributes"] = attributes;

    DestroyBuffer(&buff);
    if (atts) DestroyAttributeList(&atts);

    return out;
}

void write_file(const std::string& filename, bool is_packed, py::dict info, py::dict attributes)
{
    py::array array = info["array"].cast<py::array>();
    int nx = info["nx"].cast<int>();
    int ny = info["ny"].cast<int>();
    int nz = info.contains("nz") ? info["nz"].cast<int>() : 1;
    int nf = info["nf"].cast<int>();
    int vector_grid = info.contains("vector_grid") ? info["vector_grid"].cast<int>() : 0;
    int image_sub_type = info.contains("image_sub_type") ? info["image_sub_type"].cast<int>() : (int)BUFFER_FORMAT_IMAGE;
    bool is_float = info.contains("is_float") ? info["is_float"].cast<bool>() : true;

    BufferType buff{};
    if (!CreateBuffer(&buff, nx, ny, nz, nf, is_float, vector_grid, (BufferFormat_t)image_sub_type))
        throw std::runtime_error("Error out of memory");

    size_t nbytes = is_float ? sizeof(float) : sizeof(uint16_t);
    nbytes *= (size_t)nx * buff.totalLines;
    if ((size_t)array.nbytes() != nbytes) {
        DestroyBuffer(&buff);
        throw std::runtime_error("array size does not match nx/ny/nz/nf/image_sub_type");
    }
    std::memcpy(is_float ? (void*)buff.floatArray : (void*)buff.wordArray, array.data(), nbytes);

    if (info.contains("scaleX")) dict_to_scale(info["scaleX"].cast<py::dict>(), &buff.scaleX);
    if (info.contains("scaleY")) dict_to_scale(info["scaleY"].cast<py::dict>(), &buff.scaleY);
    if (info.contains("scaleI")) dict_to_scale(info["scaleI"].cast<py::dict>(), &buff.scaleI);

    AttributeList* atts = nullptr;
    for (auto item : attributes)
        SetAttribute(&atts, py::str(item.first).cast<std::string>().c_str(),
                             py::str(item.second).cast<std::string>().c_str());

    int err = WriteIM7(filename.c_str(), is_packed, &buff, atts);

    if (atts) DestroyAttributeList(&atts);
    DestroyBuffer(&buff);

    if (err != IMREAD_ERR_NO)
        throw std::runtime_error(error_message(err));
}

} // namespace

PYBIND11_MODULE(_core, m)
{
    m.doc() = "pybind11 binding for LaVision ReadIMX/ReadIM7 (IM7/VC7 file IO)";

    m.def("read_file", &read_file, py::arg("filename"),
          "Read an IM7/VC7/IMX/IMG/VEC file, return a dict with array, mask, attributes and metadata.");
    m.def("write_file", &write_file, py::arg("filename"), py::arg("is_packed"), py::arg("info"), py::arg("attributes"),
          "Write an IM7 file from a dict as produced by read_file().");
    m.def("get_vector_components", [](int image_sub_type) {
        return GetVectorComponents((BufferFormat_t)image_sub_type);
    }, py::arg("image_sub_type"));

    m.attr("IMREAD_ERR_NO") = (int)IMREAD_ERR_NO;
    m.attr("IMREAD_ERR_FILEOPEN") = (int)IMREAD_ERR_FILEOPEN;
    m.attr("IMREAD_ERR_HEADER") = (int)IMREAD_ERR_HEADER;
    m.attr("IMREAD_ERR_FORMAT") = (int)IMREAD_ERR_FORMAT;
    m.attr("IMREAD_ERR_DATA") = (int)IMREAD_ERR_DATA;
    m.attr("IMREAD_ERR_MEMORY") = (int)IMREAD_ERR_MEMORY;

    m.attr("BUFFER_FORMAT__NOTUSED") = (int)BUFFER_FORMAT__NOTUSED;
    m.attr("BUFFER_FORMAT_MEMPACKWORD") = (int)BUFFER_FORMAT_MEMPACKWORD;
    m.attr("BUFFER_FORMAT_FLOAT") = (int)BUFFER_FORMAT_FLOAT;
    m.attr("BUFFER_FORMAT_WORD") = (int)BUFFER_FORMAT_WORD;
    m.attr("BUFFER_FORMAT_DOUBLE") = (int)BUFFER_FORMAT_DOUBLE;
    m.attr("BUFFER_FORMAT_FLOAT_VALID") = (int)BUFFER_FORMAT_FLOAT_VALID;
    m.attr("BUFFER_FORMAT_IMAGE") = (int)BUFFER_FORMAT_IMAGE;
    m.attr("BUFFER_FORMAT_VECTOR_2D_EXTENDED") = (int)BUFFER_FORMAT_VECTOR_2D_EXTENDED;
    m.attr("BUFFER_FORMAT_VECTOR_2D") = (int)BUFFER_FORMAT_VECTOR_2D;
    m.attr("BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK") = (int)BUFFER_FORMAT_VECTOR_2D_EXTENDED_PEAK;
    m.attr("BUFFER_FORMAT_VECTOR_3D") = (int)BUFFER_FORMAT_VECTOR_3D;
    m.attr("BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK") = (int)BUFFER_FORMAT_VECTOR_3D_EXTENDED_PEAK;
    m.attr("BUFFER_FORMAT_RGB_MATRIX") = (int)BUFFER_FORMAT_RGB_MATRIX;
    m.attr("BUFFER_FORMAT_RGB_32") = (int)BUFFER_FORMAT_RGB_32;
}

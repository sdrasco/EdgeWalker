#include <pybind11/pybind11.h>
#include "strangle.h"

namespace py = pybind11;

PYBIND11_MODULE(strangle_module, m) {
    py::class_<Strangle>(m, "Strangle")
        .def(py::init<double, double, double>())
        .def("calculate_escape_ratio", &Strangle::calculate_escape_ratio)
        .def_static("calculate_probability_of_profit", &Strangle::calculate_probability_of_profit)
        .def_static("calculate_expected_gain", &Strangle::calculate_expected_gain);
}
#include <pybind11/pybind11.h>
#include "strangle.h"

namespace py = pybind11;

PYBIND11_MODULE(strangle_module, m) {
    py::class_<Strangle>(m, "Strangle")
        .def(py::init<double, double, double>())  // Constructor
        .def("calculate_escape_ratio", &Strangle::calculate_escape_ratio);  // Method binding
}

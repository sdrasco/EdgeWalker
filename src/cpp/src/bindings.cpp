#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "strangle.h"
#include "find_min_spread.h"

namespace py = pybind11;

PYBIND11_MODULE(strangle_module, m) {
    // Bind Strangle class
    py::class_<Strangle>(m, "Strangle")
        .def(py::init<double, double, double>())
        .def("calculate_escape_ratio", &Strangle::calculate_escape_ratio)
        .def_static("calculate_probability_of_profit", &Strangle::calculate_probability_of_profit)
        .def_static("calculate_expected_gain", &Strangle::calculate_expected_gain);

    // Bind Option struct with a custom constructor
    py::class_<Option>(m, "Option")
        .def(py::init<>())  // Default constructor
        .def(py::init<double, double, double, std::string>(),  // Custom constructor
             py::arg("premium"), py::arg("strike_price"),
             py::arg("implied_volatility"), py::arg("contract_type"))
        .def_readwrite("premium", &Option::premium)
        .def_readwrite("strike_price", &Option::strike_price)
        .def_readwrite("implied_volatility", &Option::implied_volatility)
        .def_readwrite("contract_type", &Option::contract_type);

    // Bind StrangleCombination struct
    py::class_<StrangleCombination>(m, "StrangleCombination")
        .def(py::init<>())  // Default constructor
        .def_readwrite("call", &StrangleCombination::call)
        .def_readwrite("put", &StrangleCombination::put)
        .def_readwrite("strangle_costs", &StrangleCombination::strangle_costs)
        .def_readwrite("upper_breakeven", &StrangleCombination::upper_breakeven)
        .def_readwrite("lower_breakeven", &StrangleCombination::lower_breakeven)
        .def_readwrite("breakeven_difference", &StrangleCombination::breakeven_difference)
        .def_readwrite("average_strike_price", &StrangleCombination::average_strike_price)
        .def_readwrite("normalized_difference", &StrangleCombination::normalized_difference);

    // Bind find_min_spread function
    m.def("find_min_spread", &find_min_spread, "Find the best strangle with minimum normalized difference",
          py::arg("calls"), py::arg("puts"));
}
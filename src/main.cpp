#include <exception>
#include <iostream>
#include <optional>
#include <string>

#include "config.hpp"

int main(int argc, char** argv) {
  try {
    std::optional<std::string> config_path = std::nullopt;
    if (argc > 1) {
      config_path = std::string(argv[1]);
    }

    const Config config = Config::Load(config_path);
    std::cout << "PiBot C++ Phase A bootstrap\n";
    std::cout << config.ToDebugString();
    return 0;
  } catch (const std::exception& ex) {
    std::cerr << "Startup failed: " << ex.what() << "\n";
    return 1;
  }
}

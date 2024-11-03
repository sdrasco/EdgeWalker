We're making some python wrapped C++ methods to speed up local calculations while keeping python's async framework.  Here's the C++ directory structure:

└── cpp/                # C++ components folder
    ├── include/        # Header files
    ├── src/            # C++ source files 
    ├── CMakeLists.txt  # CMake configuration
    └── build/          # Directory to store build artifacts 

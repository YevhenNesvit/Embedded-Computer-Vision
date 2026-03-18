cmake_minimum_required(VERSION 3.10)
project(YoloInferenceCPP)

set(CMAKE_CXX_STANDARD 17)

find_package(OpenCV REQUIRED)
find_package(Threads REQUIRED) # Додаємо пошук потоків

include_directories(${OpenCV_INCLUDE_DIRS})

add_executable(vision_engine main.cpp)

# Лінкуємо OpenCV та системні потоки (Threads)
target_link_libraries(vision_engine ${OpenCV_LIBS} Threads::Threads)
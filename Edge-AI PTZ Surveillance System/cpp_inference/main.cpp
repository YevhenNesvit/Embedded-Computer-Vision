#include <opencv2/opencv.hpp>
#include <opencv2/dnn.hpp>
#include <iostream>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include "httplib.h"

using namespace cv;
using namespace dnn;
using namespace std;

// --- ГЛОБАЛЬНІ ЗМІННІ ДЛЯ ЗВ'ЯЗКУ МІЖ ПОТОКАМИ ---
mutex frame_mutex;
Mat shared_frame;
atomic<bool> new_frame_ready(false);

mutex result_mutex;
vector<Rect> shared_boxes;
vector<int> shared_class_ids;
vector<float> shared_confidences;

atomic<bool> is_running(true);

// --- НАЛАШТУВАННЯ ТУРЕЛІ ---
const string DEVKIT_IP = "192.168.0.128"; // Твій IP для ESP32/STM32
auto last_request_time = chrono::steady_clock::now();
mutex http_mutex;

// Асинхронна функція відправки команд (аналог твого Python-коду)
void send_movement_command(int x, int y) {
    auto now = chrono::steady_clock::now();
    chrono::duration<double> elapsed = now - last_request_time;

    // Rate limiting: 10Hz (не частіше ніж раз на 0.1 сек)
    if (elapsed.count() < 0.1) {
        return; 
    }
    last_request_time = now;

    // Створюємо "демон"-потік, який відправить запит і сам закриється
    thread([x, y]() {
        httplib::Client cli(DEVKIT_IP.c_str(), 80);
        
        // Таймаут 0.2 сек (200 мілісекунд), як у твоєму Python коді
        cli.set_connection_timeout(0, 200000); 
        cli.set_read_timeout(0, 200000);

        string path = "/move?x=" + to_string(x) + "&y=" + to_string(y);
        
        // Відправляємо GET-запит. Якщо ESP32 "впала" - просто ігноруємо помилку
        if (auto res = cli.Get(path)) {
            // Успіх
        } else {
            // Fail silently
        }
    }).detach(); // detach() - це аналог daemon=True
}

// --- ПОТІК 2: ШТУЧНИЙ ІНТЕЛЕКТ ---
void ai_thread_func(Net& net) {
    Mat local_frame;
    while (is_running) {
        if (new_frame_ready) {
            {
                lock_guard<mutex> lock(frame_mutex);
                shared_frame.copyTo(local_frame);
                new_frame_ready = false;
            }

            if (local_frame.empty()) continue;

            float x_factor = local_frame.cols / 640.0f;
            float y_factor = local_frame.rows / 640.0f;

            Mat blob;
            blobFromImage(local_frame, blob, 1.0 / 255.0, Size(640, 640), Scalar(), true, false);
            net.setInput(blob);

            vector<Mat> outputs;
            net.forward(outputs, net.getUnconnectedOutLayersNames());

            // БЕЗПЕЧНА РОБОТА З ПАМ'ЯТТЮ (ВИПРАВЛЕНО)
            Mat out_mat(outputs[0].size[1], outputs[0].size[2], CV_32F, outputs[0].ptr<float>());
            Mat data_mat;
            transpose(out_mat, data_mat); // Примусово створюємо правильну матрицю

            vector<int> class_ids;
            vector<float> confidences;
            vector<Rect> boxes;

            for (int i = 0; i < 8400; ++i) {
                // Використовуємо вбудований метод OpenCV для доступу до рядків замість сирого вказівника
                float* row = data_mat.ptr<float>(i); 
                
                float max_score = -1;
                int class_id = -1;
                for (int c = 4; c < 8; ++c) {
                    if (row[c] > max_score) {
                        max_score = row[c];
                        class_id = c - 4;
                    }
                }

                // Поріг впевненості (щоб не малювати "фантомні" танки)
                if (max_score > 0.45f) {
                    float cx = row[0];
                    float cy = row[1];
                    float w = row[2];
                    float h = row[3];

                    int left = int((cx - 0.5 * w) * x_factor);
                    int top = int((cy - 0.5 * h) * y_factor);
                    int width = int(w * x_factor);
                    int height = int(h * y_factor);

                    boxes.push_back(Rect(left, top, width, height));
                    confidences.push_back(max_score);
                    class_ids.push_back(class_id);
                }
            }

            vector<int> nms_indices;
            NMSBoxes(boxes, confidences, 0.45f, 0.4f, nms_indices);

            // Записуємо знайдені танки у спільну пам'ять
            {
                lock_guard<mutex> lock(result_mutex);
                shared_boxes.clear();
                shared_class_ids.clear();
                shared_confidences.clear();
                for (int idx : nms_indices) {
                    shared_boxes.push_back(boxes[idx]);
                    shared_class_ids.push_back(class_ids[idx]);
                    shared_confidences.push_back(confidences[idx]);
                }
            }
        } else {
            this_thread::sleep_for(chrono::milliseconds(5));
        }
    }
}

// --- ПОТІК 1: ОСНОВНИЙ ВІДЕОПЛЕЄР ---
int main() {
    cout << "[INFO] С++ Vision Engine: MEMORY FIX APPLIED!" << endl;

    Net net = readNetFromONNX("best.onnx");
    net.setPreferableBackend(DNN_BACKEND_OPENCV);
    net.setPreferableTarget(DNN_TARGET_CPU);

    VideoCapture cap("video.mp4", CAP_FFMPEG);
    if (!cap.isOpened()) {
        cerr << "[ERROR] Відео не знайдено!" << endl;
        return -1;
    }

    thread ai_thread(ai_thread_func, ref(net));

    Mat frame;
    vector<Rect> local_boxes;
    vector<int> local_class_ids;
    vector<float> local_confidences;

    while (true) {
        cap >> frame;
        if (frame.empty()) break;

        if (!new_frame_ready) {
            lock_guard<mutex> lock(frame_mutex);
            frame.copyTo(shared_frame);
            new_frame_ready = true;
        }

        {
            lock_guard<mutex> lock(result_mutex);
            local_boxes = shared_boxes;
            local_class_ids = shared_class_ids;
            local_confidences = shared_confidences;
        }

        for (size_t i = 0; i < local_boxes.size(); i++) {
            Rect box = local_boxes[i];
            int cls = local_class_ids[i];
            float conf = local_confidences[i];

            Scalar color = (cls == 3) ? Scalar(0, 255, 0) : Scalar(0, 165, 255);
            rectangle(frame, box, color, 2);
            string label = "CLS: " + to_string(cls) + " | " + to_string(int(conf * 100)) + "%";
            putText(frame, label, Point(box.x, box.y - 10), FONT_HERSHEY_SIMPLEX, 0.6, color, 2);
        }

        // --- ЛОГІКА АВТОТРЕКІНГУ ---
        // Якщо ми бачимо хоча б один об'єкт - беремо перший (найбільш впевнений)
        if (!local_boxes.empty()) {
            Rect target = local_boxes[0]; 
            
            // Рахуємо центр рамки (це і є наша ціль)
            int center_x = target.x + target.width / 2;
            int center_y = target.y + target.height / 2;
            
            // Відправляємо асинхронну команду на турель!
            send_movement_command(center_x, center_y);

            // (Опціонально) Малюємо приціл по центру цілі
            circle(frame, Point(center_x, center_y), 5, Scalar(0, 0, 255), -1);
        }

        imshow("Tactical HUD C++", frame);

        if (waitKey(33) == 27) break; 
    }

    is_running = false;
    ai_thread.join(); 
    cap.release();
    destroyAllWindows();
    return 0;
}

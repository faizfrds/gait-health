#include "driver/i2c.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "mpu6050.h"
#include <stdio.h>

/* ── I2C / sensor wiring ────────────────────────────────────────────────── */
#define I2C_MASTER_SCL_IO    2              /* GPIO for I2C clock            */
#define I2C_MASTER_SDA_IO    1              /* GPIO for I2C data             */
#define I2C_MASTER_NUM       I2C_NUM_0
#define I2C_MASTER_FREQ_HZ   400000         /* 400 kHz fast-mode             */

/* ── Sampling ────────────────────────────────────────────────────────────── */
/* 100 Hz gives enough resolution to capture gait cadence (0.5–3 Hz) and
 * the higher-frequency foot-strike transients needed for step detection.    */
#define SAMPLE_PERIOD_MS     10             /* 10 ms → 100 Hz                */

/* ── Sensor placement note ──────────────────────────────────────────────── */
/* Mount the MPU-6050 on the user's ankle or shoe (dorsal side, aligned with
 * the foot's long axis) so that:
 *   AX = forward/backward (walking direction)
 *   AY = medial/lateral
 *   AZ = vertical (gravity + impact)                                        */

static const char *TAG = "gait_health";
static mpu6050_handle_t mpu6050 = NULL;

/* ── Running step counter ────────────────────────────────────────────────── */
/* Simple threshold detector on the AZ axis: a heel-strike produces a
 * downward spike followed by a recovery above 1 g. We count each rising
 * edge through the threshold as one step.                                   */
#define STEP_ACCE_THRESHOLD_G   1.2f        /* g-force peak to count a step */
static uint32_t step_count = 0;
static bool above_threshold = false;

static void update_step_count(float az)
{
    if (!above_threshold && az > STEP_ACCE_THRESHOLD_G) {
        above_threshold = true;
        step_count++;
    } else if (above_threshold && az <= STEP_ACCE_THRESHOLD_G) {
        above_threshold = false;
    }
}

/* ── I2C init ────────────────────────────────────────────────────────────── */
static void i2c_bus_init(void)
{
    i2c_config_t conf;
    conf.mode             = I2C_MODE_MASTER;
    conf.sda_io_num       = (gpio_num_t)I2C_MASTER_SDA_IO;
    conf.sda_pullup_en    = GPIO_PULLUP_ENABLE;
    conf.scl_io_num       = (gpio_num_t)I2C_MASTER_SCL_IO;
    conf.scl_pullup_en    = GPIO_PULLUP_ENABLE;
    conf.master.clk_speed = I2C_MASTER_FREQ_HZ;
    conf.clk_flags        = I2C_SCLK_SRC_FLAG_FOR_NOMAL;

    esp_err_t ret = i2c_param_config(I2C_MASTER_NUM, &conf);
    if (ret != ESP_OK) { ESP_LOGE(TAG, "I2C config error"); return; }

    ret = i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
    if (ret != ESP_OK) { ESP_LOGE(TAG, "I2C install error"); return; }
}

/* ── MPU-6050 init ───────────────────────────────────────────────────────── */
static void i2c_sensor_mpu6050_init(void)
{
    i2c_bus_init();

    mpu6050 = mpu6050_create(I2C_MASTER_NUM, MPU6050_I2C_ADDRESS);
    if (mpu6050 == NULL) { ESP_LOGE(TAG, "MPU6050 create returned NULL"); return; }

    /* ±4 g / ±500 °/s — wide enough for vigorous walking, tight enough for
     * good resolution during normal gait.                                   */
    esp_err_t ret = mpu6050_config(mpu6050, ACCE_FS_4G, GYRO_FS_500DPS);
    if (ret != ESP_OK) { ESP_LOGE(TAG, "MPU6050 config error"); return; }

    ret = mpu6050_wake_up(mpu6050);
    if (ret != ESP_OK) { ESP_LOGE(TAG, "MPU6050 wake up error"); return; }
}

/* ── Main ────────────────────────────────────────────────────────────────── */
void app_main(void)
{
    esp_err_t ret;
    uint8_t device_id;
    mpu6050_acce_value_t acce;
    mpu6050_gyro_value_t gyro;
    mpu6050_temp_value_t temp;

    i2c_sensor_mpu6050_init();

    ret = mpu6050_get_deviceid(mpu6050, &device_id);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to read device ID");
    } else {
        ESP_LOGI(TAG, "MPU6050 device ID: 0x%02X", device_id);
    }

    /* Print CSV header once so a host-side logger can parse columns easily. */
    ESP_LOGI(TAG, "ts_us,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,temp_c,steps");

    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t period   = pdMS_TO_TICKS(SAMPLE_PERIOD_MS);

    while (1) {
        ret = mpu6050_get_acce(mpu6050, &acce);
        if (ret != ESP_OK) { ESP_LOGE(TAG, "Acce read failed"); }

        ret = mpu6050_get_gyro(mpu6050, &gyro);
        if (ret != ESP_OK) { ESP_LOGE(TAG, "Gyro read failed"); }

        ret = mpu6050_get_temp(mpu6050, &temp);
        if (ret != ESP_OK) { ESP_LOGE(TAG, "Temp read failed"); }

        /* Update step counter based on vertical acceleration (AZ). */
        update_step_count(acce.acce_z);

        /* Emit one CSV row per sample.
         * ts_us  — microseconds since boot (monotonic, wraps ~72 min)
         * ax/ay/az — acceleration in g
         * gx/gy/gz — angular rate in °/s
         * temp_c — die temperature (useful for drift correction)
         * steps  — cumulative step count since power-on               */
        ESP_LOGI(TAG, "%lld,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.2f,%lu",
                 (long long)esp_timer_get_time(),
                 acce.acce_x, acce.acce_y, acce.acce_z,
                 gyro.gyro_x, gyro.gyro_y, gyro.gyro_z,
                 temp.temp,
                 (unsigned long)step_count);

        vTaskDelayUntil(&last_wake_time, period);
    }
}

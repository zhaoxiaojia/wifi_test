# Database Schema

## Tables
### `artifact`

**Columns**
- `test_report_id`: INT NOT NULL
- `file_name`: VARCHAR(255) NOT NULL
- `content_type`: VARCHAR(128) NOT NULL
- `sha256`: CHAR(64) NOT NULL
- `size_bytes`: INT NOT NULL
- `content`: LONGBLOB NOT NULL

**Indexes**
- `idx_artifact_report`: INDEX idx_artifact_report (`test_report_id`, `created_at`)
- `idx_artifact_sha`: INDEX idx_artifact_sha (`sha256`)

**Constraints**
- `uq_artifact_report`: CONSTRAINT uq_artifact_report UNIQUE (`test_report_id`)
- `fk_artifact_report`: CONSTRAINT fk_artifact_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`) ON DELETE CASCADE

### `compatibility`

**Columns**
- `execution_id`: INT NOT NULL
- `router_id`: INT NULL DEFAULT NULL
- `pdu_ip`: VARCHAR(64)
- `pdu_port`: INT
- `ap_brand`: VARCHAR(255)
- `band`: VARCHAR(32)
- `ssid`: VARCHAR(255)
- `wifi_mode`: VARCHAR(64)
- `bandwidth`: VARCHAR(64)
- `security`: VARCHAR(64)
- `scan_result`: VARCHAR(32)
- `connect_result`: VARCHAR(32)
- `tx_result`: VARCHAR(64)
- `tx_channel`: VARCHAR(64)
- `tx_rssi`: VARCHAR(64)
- `tx_criteria`: VARCHAR(64)
- `tx_throughput_mbps`: VARCHAR(64)
- `rx_result`: VARCHAR(64)
- `rx_channel`: VARCHAR(64)
- `rx_rssi`: VARCHAR(64)
- `rx_criteria`: VARCHAR(64)
- `rx_throughput_mbps`: VARCHAR(64)

**Indexes**
- `idx_compat_report`: INDEX idx_compat_report (`execution_id`)
- `idx_compat_router`: INDEX idx_compat_router (`router_id`)

**Constraints**
- `fk_compat_report`: CONSTRAINT fk_compat_report FOREIGN KEY (`execution_id`) REFERENCES `execution`(`id`) ON DELETE CASCADE
- `fk_compat_router`: CONSTRAINT fk_compat_router FOREIGN KEY (`router_id`) REFERENCES `router`(`id`)

### `dut`

**Columns**
- `serial_number`: VARCHAR(255)
- `connect_type`: VARCHAR(64)
- `mac_address`: VARCHAR(64)
- `adb_device`: VARCHAR(128)
- `telnet_ip`: VARCHAR(128)
- `software_version`: VARCHAR(128)
- `driver_version`: VARCHAR(128)
- `android_version`: VARCHAR(64)
- `kernel_version`: VARCHAR(64)
- `payload_json`: JSON

**Indexes**
- `idx_dut_created_at`: INDEX idx_dut_created_at (`created_at`)

### `execution`

**Columns**
- `test_report_id`: INT NOT NULL
- `run_type`: VARCHAR(64) NOT NULL
- `dut_id`: INT NOT NULL
- `router_name`: VARCHAR(128)
- `router_address`: VARCHAR(128)
- `lab_id`: INT NULL DEFAULT NULL
- `bt_mode`: VARCHAR(64)
- `bt_ble_alias`: VARCHAR(128)
- `bt_classic_alias`: VARCHAR(128)
- `csv_name`: VARCHAR(255) NOT NULL
- `csv_path`: VARCHAR(512)
- `run_source`: VARCHAR(32)
- `duration_seconds`: INT NULL DEFAULT NULL
- `payload_json`: JSON

**Indexes**
- `idx_test_run_case`: INDEX idx_test_run_case (`test_report_id`)
- `idx_test_run_dut`: INDEX idx_test_run_dut (`dut_id`)
- `idx_test_run_type`: INDEX idx_test_run_type (`run_type`)
- `idx_test_run_created_at`: INDEX idx_test_run_created_at (`created_at`)

**Constraints**
- `fk_test_run_case`: CONSTRAINT fk_test_run_case FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`) ON DELETE CASCADE
- `fk_test_run_dut`: CONSTRAINT fk_test_run_dut FOREIGN KEY (`dut_id`) REFERENCES `dut`(`id`)
- `fk_test_run_lab`: CONSTRAINT fk_test_run_lab FOREIGN KEY (`lab_id`) REFERENCES `lab`(`id`)

### `lab`

**Columns**
- `lab_name`: VARCHAR(255) NOT NULL
- `capabilities`: JSON
- `turntable_model`: VARCHAR(64)
- `rf_model`: VARCHAR(64)
- `payload_json`: JSON

**Indexes**
- `idx_lab_name`: INDEX idx_lab_name (`lab_name`)

**Constraints**
- `uq_lab_name`: CONSTRAINT uq_lab_name UNIQUE (`lab_name`)

### `perf_metric_kv`

**Columns**
- `execution_id`: INT NOT NULL
- `metric_name`: VARCHAR(64) NOT NULL
- `metric_unit`: VARCHAR(16)
- `metric_value`: DECIMAL(12,4) NOT NULL
- `stage`: VARCHAR(64)

**Indexes**
- `idx_kv_report`: INDEX idx_kv_report (`execution_id`)
- `idx_kv_name`: INDEX idx_kv_name (`metric_name`, `stage`)

**Constraints**
- `fk_kv_report`: CONSTRAINT fk_kv_report FOREIGN KEY (`execution_id`) REFERENCES `execution`(`id`) ON DELETE CASCADE

### `performance`

**Columns**
- `test_report_id`: INT NOT NULL
- `execution_id`: INT NOT NULL
- `csv_name`: VARCHAR(255) NOT NULL
- `data_type`: VARCHAR(64)
- `serial_number`: VARCHAR(255) NULL DEFAULT NULL COMMENT 'SerianNumber'
- `test_category`: VARCHAR(255) NULL DEFAULT NULL COMMENT 'Test_Category'
- `standard`: ENUM('11a','11b','11g','11n','11ac','11ax','11be') NULL DEFAULT NULL COMMENT 'Standard'
- `band`: ENUM('2.4','5','6') NULL DEFAULT NULL COMMENT 'Freq_Band'
- `bandwidth_mhz`: SMALLINT NULL DEFAULT NULL COMMENT 'BW'
- `phy_rate_mbps`: DECIMAL(10,3) NULL DEFAULT NULL COMMENT 'Data_Rate'
- `center_freq_mhz`: SMALLINT NULL DEFAULT NULL COMMENT 'CH_Freq_MHz'
- `protocol`: VARCHAR(255) NULL DEFAULT NULL COMMENT 'Protocol'
- `mode`: VARCHAR(64) NULL DEFAULT NULL COMMENT 'Mode'
- `direction`: ENUM('uplink','downlink','bi') NULL DEFAULT NULL COMMENT 'Direction'
- `total_path_loss`: DECIMAL(6,2) NULL DEFAULT NULL COMMENT 'Total_Path_Loss'
- `path_loss_db`: DECIMAL(6,2) NULL DEFAULT NULL COMMENT 'DB'
- `rssi`: DECIMAL(6,2) NULL DEFAULT NULL COMMENT 'RSSI'
- `angle_deg`: DECIMAL(6,2) NULL DEFAULT NULL COMMENT 'Angel'
- `mcs_rate`: VARCHAR(255) NULL DEFAULT NULL COMMENT 'MCS_Rate'
- `throughput_peak_mbps`: DECIMAL(10,3) NULL DEFAULT NULL COMMENT 'Max_Rate'
- `throughput_avg_mbps`: DECIMAL(10,3) NULL DEFAULT NULL COMMENT 'Throughput'
- `target_throughput_mbps`: DECIMAL(10,3) NULL DEFAULT NULL COMMENT 'Expect_Rate'
- `latency_ms`: DECIMAL(10,3) NULL DEFAULT NULL COMMENT 'Latency'
- `packet_loss`: VARCHAR(64) NULL DEFAULT NULL COMMENT 'Packet_Loss'
- `profile_mode`: VARCHAR(64) NULL DEFAULT NULL COMMENT 'Profile_Mode'
- `profile_value`: VARCHAR(64) NULL DEFAULT NULL COMMENT 'Profile_Value'
- `scenario_group_key`: VARCHAR(255) NULL DEFAULT NULL COMMENT 'Scenario_Group_Key'

**Indexes**
- `idx_performance_report`: INDEX idx_performance_report (`execution_id`)
- `idx_performance_test_report`: INDEX idx_performance_test_report (`test_report_id`)
- `idx_performance_band`: INDEX idx_performance_band (`band`, `bandwidth_mhz`, `standard`)
- `idx_performance_created_at`: INDEX idx_performance_created_at (`created_at`)

**Constraints**
- `fk_performance_report`: CONSTRAINT fk_performance_report FOREIGN KEY (`execution_id`) REFERENCES `execution`(`id`) ON DELETE CASCADE
- `fk_performance_test_report`: CONSTRAINT fk_performance_test_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`) ON DELETE CASCADE

### `project`

**Columns**
- `brand`: VARCHAR(64) NOT NULL
- `product_line`: VARCHAR(64) NOT NULL
- `project_name`: VARCHAR(128) NOT NULL
- `project_display_name`: VARCHAR(256)
- `main_chip`: VARCHAR(64)
- `wifi_module`: VARCHAR(64)
- `interface`: VARCHAR(64)
- `ecosystem`: VARCHAR(64)
- `mass_production_status`: JSON
- `payload_json`: JSON

**Indexes**
- `idx_project_name`: INDEX idx_project_name (`project_name`)

**Constraints**
- `uq_project_name`: CONSTRAINT uq_project_name UNIQUE (`project_name`)

### `router`

**Columns**
- `ip`: VARCHAR(64) NOT NULL
- `port`: INT NOT NULL
- `brand`: VARCHAR(128)
- `model`: VARCHAR(128)
- `payload_json`: JSON

**Indexes**
- `idx_router_ip_port`: INDEX idx_router_ip_port (`ip`, `port`)

**Constraints**
- `uq_router_ip_port`: CONSTRAINT uq_router_ip_port UNIQUE (`ip`, `port`)

### `test_report`

**Columns**
- `project_id`: INT NOT NULL
- `report_name`: VARCHAR(255) NOT NULL
- `case_path`: VARCHAR(512)
- `is_golden`: TINYINT(1) NOT NULL DEFAULT 0
- `report_type`: VARCHAR(64)
- `golden_group`: VARCHAR(32)
- `notes`: TEXT

**Indexes**
- `idx_test_case_project`: INDEX idx_test_case_project (`project_id`)
- `idx_test_case_golden_group`: INDEX idx_test_case_golden_group (`project_id`, `report_type`, `golden_group`)
- `idx_test_case_created_at`: INDEX idx_test_case_created_at (`created_at`)

**Constraints**
- `uq_test_case_project_name`: CONSTRAINT uq_test_case_project_name UNIQUE (`project_id`, `report_name`)
- `uq_test_case_project_type_golden`: CONSTRAINT uq_test_case_project_type_golden UNIQUE (`project_id`, `report_type`, `golden_group`)
- `fk_test_report_project`: CONSTRAINT fk_test_report_project FOREIGN KEY (`project_id`) REFERENCES `project`(`id`) ON DELETE CASCADE

## Views
### `v_perf_latest`

```sql
SELECT
            ranked.id,
            ranked.execution_id,
            ranked.csv_name,
            ranked.data_type,
            ranked.serial_number,
            ranked.test_category,
            ranked.standard,
            ranked.band,
            ranked.bandwidth_mhz,
            ranked.phy_rate_mbps,
            ranked.center_freq_mhz,
            ranked.protocol,
            ranked.direction,
            ranked.total_path_loss,
            ranked.path_loss_db,
            ranked.rssi,
            ranked.angle_deg,
            ranked.mcs_rate,
            ranked.throughput_peak_mbps,
            ranked.throughput_avg_mbps,
            ranked.target_throughput_mbps,
            ranked.created_at,
            ranked.updated_at,
            ranked.project_id,
            ranked.report_case_path AS case_path,
            ranked.execution_type
        FROM (
            SELECT
                p.*,
                tr.project_id,
                tr.case_path AS report_case_path,
                ex.run_type AS execution_type,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.project_id, tr.case_path, p.band, p.bandwidth_mhz, ex.run_type
                    ORDER BY p.created_at DESC, p.id DESC
                ) AS rn
            FROM performance AS p
            JOIN execution AS ex ON ex.id = p.execution_id
            JOIN test_report AS tr ON tr.id = ex.test_report_id
        ) AS ranked
        WHERE ranked.rn = 1
```

### `v_run_overview`

```sql
SELECT
            p.id AS project_id,
            p.brand,
            p.product_line,
            p.project_name,
            p.main_chip,
            p.wifi_module,
            p.interface,
            p.ecosystem,
            p.mass_production_status,
            tc.id AS test_report_id,
            tc.report_name AS case_name,
            tc.case_path AS case_path,
            tc.created_at AS case_created_at,
            tc.updated_at AS case_updated_at,
            tr.id AS execution_id,
            tr.run_type,
            d.serial_number,
            d.connect_type,
            d.adb_device,
            d.telnet_ip,
            d.software_version,
            d.driver_version,
            d.android_version,
            d.kernel_version,
            tr.router_name,
            tr.router_address,
            l.rf_model,
            l.turntable_model AS corner_model,
            l.lab_name,
            tr.csv_name,
            tr.csv_path,
            tr.run_source,
            tr.duration_seconds,
            tr.created_at AS test_run_created_at,
            agg.throughput_avg_max_mbps,
            agg.throughput_peak_max_mbps,
            agg.throughput_avg_mean_mbps,
            agg.target_throughput_avg_mbps
        FROM project AS p
        JOIN test_report AS tc ON tc.project_id = p.id
        JOIN execution AS tr ON tr.test_report_id = tc.id
        JOIN dut AS d ON d.id = tr.dut_id
        LEFT JOIN lab AS l ON l.id = tr.lab_id
        LEFT JOIN (
            SELECT
                execution_id,
                MAX(throughput_avg_mbps) AS throughput_avg_max_mbps,
                MAX(throughput_peak_mbps) AS throughput_peak_max_mbps,
                AVG(throughput_avg_mbps) AS throughput_avg_mean_mbps,
                AVG(target_throughput_mbps) AS target_throughput_avg_mbps
            FROM performance
            GROUP BY execution_id
        ) AS agg ON agg.execution_id = tr.id
```

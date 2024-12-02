package com.example.btconnect

import android.app.Activity
import android.bluetooth.BluetoothAdapter
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts

import com.permissionx.guolindev.PermissionX
import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothSocket
import android.bluetooth.le.BluetoothLeScanner
import android.content.Context
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.BroadcastReceiver
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import java.io.IOException
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private val bluetoothAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()
    private var bluetoothSocket: BluetoothSocket? = null
    private var bluetoothLeScanner: BluetoothLeScanner? = null
    private var scanning = false
    private var bluetoothGatt: BluetoothGatt? = null
    private val handler = Handler(Looper.getMainLooper())
    private var targetDevice: BluetoothDevice? = null

    // 扫描时的超时时间
    private val SCAN_PERIOD: Long = 300000
    private val uuid: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB") // 通用 UUID
    private var targetDeviceName: String = "DefaultDevice"
    private var targetAction: String = "DefaultAction"
    private val TAG = "btConnect"

    private val bluetoothPermissions = arrayOf(
        Manifest.permission.BLUETOOTH_CONNECT,
        Manifest.permission.BLUETOOTH_SCAN
    )

    private fun checkAndRequestPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val permissionsNeeded = bluetoothPermissions.filter {
                ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
            }
            if (permissionsNeeded.isNotEmpty()) {
                ActivityCompat.requestPermissions(this, permissionsNeeded.toTypedArray(), 1001)
            }
        }
    }
    @SuppressLint("MissingPermission")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        Log.d(TAG, "onCreate")
        if (bluetoothAdapter == null) {
            Toast.makeText(this, "设备不支持蓝牙", Toast.LENGTH_SHORT).show()
            finish()
        }

        // 确保蓝牙已开启
        if (bluetoothAdapter?.isEnabled == false) {
            val enableBtIntent = Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)
            startActivityForResult(enableBtIntent, 1)
        }
        checkAndRequestPermissions()
        // 注册广播接收器，监听发现的设备
        val filter = IntentFilter(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
        registerReceiver(bondStateReceiver, filter)
        val intent = intent
        targetDeviceName = intent.getStringExtra("device").toString() ?: "JBL GO 2"
        targetAction = intent.getStringExtra("action").toString() ?: "connect"
        Log.d(TAG, "$targetAction $targetDeviceName")
        if (targetAction == "connect") {
            // 启动搜索蓝牙设备
            startDiscoveryAndPairing()
            startBLEScan()
        } else {
            Log.d(TAG, "disconnect")
        }

    }

    @SuppressLint("MissingPermission")
    private fun startDiscoveryAndPairing() {
        if (bluetoothAdapter == null) {
            Toast.makeText(this, "设备不支持蓝牙", Toast.LENGTH_SHORT).show()
            return
        }

        if (bluetoothAdapter.isDiscovering) {
            bluetoothAdapter.cancelDiscovery()
        }

        bluetoothAdapter.startDiscovery()

        // 搜索设备并自动尝试配对
        val filter = IntentFilter(BluetoothDevice.ACTION_FOUND)
        registerReceiver(object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                val action = intent.action
                if (BluetoothDevice.ACTION_FOUND == action) {
                    val device =
                        intent.getParcelableExtra<BluetoothDevice>(BluetoothDevice.EXTRA_DEVICE)
                    Log.d(TAG, ("class " + device?.name) ?: "null")
                    if (device != null && device.name == targetDeviceName) {
                        bluetoothAdapter.cancelDiscovery()
                        Log.d(TAG, "start pair")
                        // 检查是否已配对
                        if (device.bondState == BluetoothDevice.BOND_NONE) {
                            pairDevice(device)
                        } else {
                            Log.d(TAG, "设备已配对")
                        }
                    }
                }
            }
        }, filter)
    }

    @SuppressLint("MissingPermission")
    private fun pairDevice(device: BluetoothDevice) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            device.createBond()
        } else {
            try {
                val method = device.javaClass.getMethod("createBond")
                method.invoke(device)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private val bondStateReceiver = object : BroadcastReceiver() {
        @SuppressLint("MissingPermission")
        override fun onReceive(context: Context?, intent: Intent?) {
            val action = intent?.action
            if (BluetoothDevice.ACTION_BOND_STATE_CHANGED == action) {
                val device =
                    intent.getParcelableExtra<BluetoothDevice>(BluetoothDevice.EXTRA_DEVICE)
                val bondState = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, -1)

                when (bondState) {
                    BluetoothDevice.BOND_BONDING -> {
                        Toast.makeText(
                            this@MainActivity, "正在配对 ${device?.name}", Toast.LENGTH_SHORT
                        ).show()
                    }

                    BluetoothDevice.BOND_BONDED -> {
                        Toast.makeText(
                            this@MainActivity, "已配对 ${device?.name}", Toast.LENGTH_SHORT
                        ).show()
                    }

                    BluetoothDevice.BOND_NONE -> {
                        Toast.makeText(this@MainActivity, "配对失败或取消配对", Toast.LENGTH_SHORT)
                            .show()
                    }
                }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun startBLEScan() {
        // 开始扫描
        val scanCallback = object : ScanCallback() {
            @SuppressLint("MissingPermission")
            override fun onScanResult(callbackType: Int, result: ScanResult?) {
                super.onScanResult(callbackType, result)
                result?.device?.let { device ->
                    Log.d(TAG, ("ble " + device?.name) ?: "null")
                    // 处理扫描到的设备
                    if (device.name == targetDeviceName) {
                        Toast.makeText(
                            this@MainActivity, "发现设备: ${device.name}", Toast.LENGTH_SHORT
                        ).show()
                        connectToDevice(device)
                    }
                }
            }

            override fun onScanFailed(errorCode: Int) {
                Toast.makeText(this@MainActivity, "扫描失败: $errorCode", Toast.LENGTH_SHORT).show()
            }
        }

        // 停止扫描的 Runnable
        val stopScanRunnable = Runnable {
            if (scanning) {
                bluetoothLeScanner?.stopScan(scanCallback)
                scanning = false
                Log.d(TAG, "ble扫描结束")
            }
        }

        // 开始扫描
        scanning = true
        bluetoothLeScanner?.startScan(null, ScanSettings.Builder().build(), scanCallback)
        Log.d(TAG, "开始扫描 BLE 设备...")

        // 设置超时停止扫描
        handler.postDelayed(stopScanRunnable, SCAN_PERIOD)
    }

    private fun connectToDevice(device: BluetoothDevice) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (ActivityCompat.checkSelfPermission(
                    this, Manifest.permission.BLUETOOTH_CONNECT
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(arrayOf(Manifest.permission.BLUETOOTH_CONNECT), 1002)
                return
            }
        }

        bluetoothGatt = device.connectGatt(this, false, object : BluetoothGattCallback() {
            @SuppressLint("MissingPermission")
            override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
                super.onConnectionStateChange(gatt, status, newState)
                when (newState) {
                    BluetoothGatt.STATE_CONNECTED -> {
                        Log.d(TAG, "连接成功")
                        gatt.discoverServices() // 开始发现服务
                    }

                    BluetoothGatt.STATE_DISCONNECTED -> {
                        Log.d(TAG, "连接断开")
                    }
                }
            }

            override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
                super.onServicesDiscovered(gatt, status)
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    val services = gatt.services
                    Log.d(TAG, "发现服务: ${services.size}")
                    // 示例：获取第一个服务的特征
                    val characteristic = services[0].characteristics[0]
                    readCharacteristic(gatt, characteristic)
                }
            }

            override fun onCharacteristicRead(
                gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int
            ) {
                super.onCharacteristicRead(gatt, characteristic, status)
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    val value = characteristic.value
                    Log.d(TAG, "读取到数据: ${value.contentToString()}")
                }
            }
        })
    }


    @SuppressLint("MissingPermission")
    private fun readCharacteristic(
        gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic
    ) {
        gatt.readCharacteristic(characteristic)
    }

    private fun disconnect() {
        try {
            bluetoothSocket?.close()
            Log.d(TAG, "连接已断开")
        } catch (e: IOException) {
            e.printStackTrace()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        unregisterReceiver(bondStateReceiver)
        disconnect()
    }
}

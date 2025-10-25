#cs ----------------------------------------------------------------------------

 AutoIt Version: 3.3.16.1
 Author:         myName

 Script Function:
	Template AutoIt script.

#ce ----------------------------------------------------------------------------
; 更新角度数据的方法 - 修正版本
Func UpdateAngle($angle)
    ; 确保输入的是有效的数字
    If Not StringIsDigit(StringReplace($angle, "-", "")) Then
        MsgBox(16, "错误", "角度值无效: " & $angle)
        Return False
    EndIf

    ; 获取当前角度并计算预计时间
    Local $currentAngle = GetAngle()
    Local $angleDiff = Abs($currentAngle - Number($angle))
    Local $estimatedTime = Int($angleDiff / 60 * 1000) + 2000 ; 计算时间+2秒缓冲

    ; 执行角度设置操作
    WinActivate($windowTitle)
    Sleep(200)
    ControlClick($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Sleep(100)
    ControlFocus($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")

    ; 清空并输入新值
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", "^a") ; Ctrl+A全选
    Sleep(50)
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", "{DEL}") ; 删除
    Sleep(50)
    ControlSend($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11", $angle) ; 输入新值
    Sleep(100)

    ControlClick($windowTitle, "", "WindowsForms10.BUTTON.app.0.141b42a_r39_ad14")
    Sleep(500)

    ; 等待移动完成
    Local $startTime = TimerInit()
    Local $timeout = $estimatedTime + 5000 ; 预计时间+5秒缓冲
    Local $lastPrintTime = TimerInit()

    While TimerDiff($startTime) < $timeout
        Local $buttonState = ControlCommand($windowTitle, "", "WindowsForms10.BUTTON.app.0.141b42a_r39_ad14", "IsEnabled", "")

        If $buttonState Then
            Local $actualTime = Int(TimerDiff($startTime) / 1000)
            ExitLoop
        EndIf

        ; 每3秒打印一次状态
        If TimerDiff($lastPrintTime) >= 3000 Then
            Local $elapsed = Int(TimerDiff($startTime) / 1000)
            $lastPrintTime = TimerInit()
        EndIf

        Sleep(1000) ; 每秒检查一次
    WEnd

    ; 检查是否超时
    If TimerDiff($startTime) >= $timeout Then
        ConsoleWrite("移动超时，但继续执行" & @CRLF)
    EndIf

    Sleep(1000) ; 稳定等待
    Return True
EndFunc


; 更新距离数据的方法
Func UpdateDistance($distance)
    ; 这里可以添加处理距离数据的逻辑
    ControlFocus($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13")
    ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", "{CTRL}a") ; 全选
    Sleep(100)
    ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", $distance) ; 使用参数$distance
    Sleep(100)
    ControlFocus($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad16")
    ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad16")
EndFunc

Func GetAngle()
    ControlClick($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Local $currentAngle = ControlGetText($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
    Sleep(1000)
    Return $currentAngle
EndFunc

Func GetDistance()
    ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad14")
    Local $currentDistance = ControlGetText($windowTitle, "", "WindowsForms10.EDIT.app.0.141b42a_r8_ad13")
    Sleep(1000)
    Return $currentDistance
EndFunc

Func GetData()
    Local $currentAngle = GetAngle()
    Local $currentDistance = GetDistance()
    Local $result = $currentAngle & "|" & $currentDistance
    ConsoleWrite($result & @CRLF) ; 输出到 stdout
EndFunc

; 定义软件路径
Local $softwarePath = "Sunvey.ControllerTool.exe" ; 请将路径替换为实际的路径

; 定义窗口标题
Local $windowTitle = "System24"

; 检查软件是否已经在运行
If WinExists($windowTitle) Then
    ; 软件已经在运行，激活窗口并退出脚本
    WinActivate($windowTitle)
    MsgBox(0, "提示", "软件已经在运行中！",1)
Else
    ; 软件未运行，启动软件
    Run($softwarePath)

    ; 等待软件窗口出现
    WinWait($windowTitle, "", 10) ; 等待最多10秒

EndIf

; 初始化变量
Local $distanceData = ""
Local $angleData = ""

; 解析命令行参数
For $i = 1 To $CmdLine[0]
    If $CmdLine[$i] = "-distance" And $i + 1 <= $CmdLine[0] Then
        $distanceData = $CmdLine[$i + 1]
    ElseIf $CmdLine[$i] = "-angle" And $i + 1 <= $CmdLine[0] Then
        $angleData = $CmdLine[$i + 1]
    EndIf
Next

; 判断并处理距离数据
If $distanceData <> "" Then
    UpdateDistance($distanceData)
    Sleep(1000)
EndIf

; 判断并处理角度数据
If $angleData <> "" Then
    Local $currentAngle = GetAngle()
    UpdateAngle($angleData)
    ; 确保$currentAngle是数字类型
    If IsNumber($currentAngle) Or StringIsDigit($currentAngle) Then
        Local $gap = Abs(Number($currentAngle) - Number($angleData))
        MsgBox(0,"","旋转的角度为 :" & $gap,1)
        Sleep(1000 * $gap /6)
    Else
        MsgBox(0,"","当前角度获取失败",1)
    EndIf
EndIf

GetData()
MsgBox(0,"","Done",1)
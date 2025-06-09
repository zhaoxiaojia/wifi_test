#cs ----------------------------------------------------------------------------

 AutoIt Version: 3.3.16.1
 Author:         myName

 Script Function:
	Template AutoIt script.

#ce ----------------------------------------------------------------------------

; Script Start - Add your code below here

; 更新角度数据的方法
Func UpdateAngle($angle)
    ; 这里可以添加处理角度数据的逻辑
	ControlFocus($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r39_ad11")
	ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r39_ad11", "")
	Sleep(1000)
	ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r39_ad11", $angleData)
	ControlFocus($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r39_ad11")
	ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r39_ad11")
EndFunc

; 更新距离数据的方法
Func UpdateDistance($distance)
    ; 这里可以添加处理距离数据的逻辑
	ControlFocus($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13")
	ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", "")
	Sleep(1000)
	ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad13", $distanceData)
	ControlFocus($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad16")
	ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad16")
EndFunc

Func GetAngle()
	ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r39_ad18")
	Local $currentAngle = ControlGetText($windowTitle, "", "WindowsForms10.BUTTON.app.0.141b42a_r39_ad18")
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

; 运行软件
Run($softwarePath)

; 等待软件窗口出现
; 假设窗口标题为 "System24"
Local $windowTitle = "System24"
WinWait($windowTitle, "", 10) ; 等待最多10秒

; 检查窗口是否成功打开
If WinExists($windowTitle) Then
    MsgBox(0, "Success", "Sunvey.ControllerTool.exe has been opened successfully.",1)
Else
    MsgBox(16, "Error", "Failed to open Sunvey.ControllerTool.exe",1)
EndIf

; 检查 距离和角度参数
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
	Local $gap = Abs($currentAngle - $angleData)
	MsgBox(0,"","旋转的角度为 :" & $gap,1)
	Sleep(1000 * $gap /6)
EndIf



GetData()
MsgBox(0,"","Done",1)
WinClose($windowTitle)
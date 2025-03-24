#cs ----------------------------------------------------------------------------

 AutoIt Version: 3.3.16.1
 Author:         myName

 Script Function:
	Template AutoIt script.

#ce ----------------------------------------------------------------------------

; Script Start - Add your code below here


; 定义软件路径
Local $softwarePath = "ACUControlTool.exe" ; 请将路径替换为实际的路径

; 运行软件
Run($softwarePath)

; 等待软件窗口出现
; 假设窗口标题为 "ACUControlTool"
Local $windowTitle = "AcuControlTool"
WinWait($windowTitle, "", 10) ; 等待最多10秒

; 检查窗口是否成功打开
If WinExists($windowTitle) Then
    MsgBox(0, "Success", "ACUControlTool has been opened successfully.",1)
Else
    MsgBox(16, "Error", "Failed to open ACUControlTool.",1)
EndIf

ControlFocus($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad11")
ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad11","")
Sleep(1000)
ControlSend($windowTitle,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad11",$CmdLine[1])
Sleep(1000)
ControlFocus($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
ControlClick($windowTitle,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
Local $startTime = TimerInit()
While True
    Local $currentText = ControlGetText($windowTitle, "", "WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad11")

    ; 检查是否包含目标信息
    If StringInStr($currentText, " success.") > 0 Then
        MsgBox(0, "Success", "目标信息已找到：" & $currentText,1)
        ExitLoop
    EndIf

    ; 检查是否超时
    If TimerDiff($startTime) >= 5 * 1000 Then
        MsgBox(16, "Error", "等待超时，未找到目标信息。",1)
        ExitLoop
    EndIf

    Sleep(500)
WEnd
Sleep(3000)
WinClose($windowTitle)
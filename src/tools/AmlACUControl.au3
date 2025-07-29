; 设置AutoIt脚本编码为UTF-8带BOM格式，确保中文正常显示
#Region ;**** 脚本元信息 ****
#AutoIt3Wrapper_Icon=
#AutoIt3Wrapper_Outfile=ACUController.exe
#AutoIt3Wrapper_Compression=4       ; 压缩等级
#AutoIt3Wrapper_UseUpx=y           ; 使用UPX压缩
#AutoIt3Wrapper_UseAnsi=n          ; 禁用ANSI编码，防止中文乱码
#EndRegion ;**** 脚本元信息 ****

#include <MsgBoxConstants.au3>

; 常量定义
Global Const $TARGET_EXE = "ACUControlTool.exe"    ; 目标程序文件名
Global Const $TARGET_TITLE = "AcuControlTool"      ; 目标窗口标题


; ============= 函数定义 =============

; 显示错误信息（统一处理编码问题）
Func ShowError($title, $message)
    MsgBox(16, $title, $message,2)
EndFunc

; 处理ACUControlTool程序
Func HandleACUControlTool()
    ; 检查程序是否已运行
    If ProcessExists($TARGET_EXE) Then
        MsgBox(0,"","程序已在运行，尝试激活窗口..." & @CRLF,2)
                
        ; 方案1：通过窗口标题激活
        Local $hWnd = WinGetHandle($TARGET_TITLE)
	
        If $hWnd Then
            WinActivate($hWnd)
            WinSetState($hWnd, "", @SW_RESTORE)  ; 确保窗口不是最小化状态
            ControlFocus($hWnd, "", "")           ; 设置光标焦点
            ; 尝试将窗口置前（解决被遮挡情况）
            WinSetOnTop($hWnd, "", 1)
            Sleep(2000)            
            Return
	EndIf        
    
    Else
        ; 程序未运行，启动它
	
        MsgBox(0,"","启动程序: " & $TARGET_EXE & @CRLF,1)
        
        Local $iPID = Run($TARGET_EXE)
        If @error Then
            ShowError("启动失败", "无法启动 " & $TARGET_EXE)
            Exit(3)
        EndIf
        
        ; 等待窗口出现（带超时检测）
        Local $hWnd = WinWait($TARGET_TITLE, "", 5)
        If $hWnd = 0 Then
            MsgBox(0,"","警告：程序已启动但未检测到窗口" & @CRLF,1)
        Else
            MsgBox(0,"","程序启动成功，窗口句柄: " & $hWnd & @CRLF,1)
        EndIf
    EndIf
EndFunc

; 等待控件出现，超时自动报错并退出
Func WaitForControlEx($sTitle, $sControlID, $iTimeout = 10, $bExitOnFail = True)
    Local $hControl = 0
    Local $iStartTime = TimerInit()
    While TimerDiff($iStartTime) < $iTimeout * 1000
        $hControl = ControlGetHandle($sTitle, "", $sControlID)
        If $hControl <> 0 Then Return $hControl
        Sleep(100)
	Sleep(1000)
    WEnd
    
    ; 超时处理
    If $bExitOnFail Then
        MsgBox(16, "错误", "控件 [" & $sControlID & "] 未在 " & $iTimeout & " 秒内出现！")
        Exit
    EndIf
    
    Return 0
EndFunc

Func Init()
	#comments-start

	;点击Usb Control
	Local $hControl = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad13")
	ControlClick($TARGET_TITLE,"",$hControl)
	Sleep(1000)
	$hControl = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad19")
	ControlClick($TARGET_TITLE,"",$hControl)

	;确认 弹窗
	Send("{ENTER}")
	Sleep(1000)
	;输入需要开启的端口
	ControlClick($TARGET_TITLE,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad12")
	Sleep(1000)
	; 通过窗口句柄和控件句柄操作
	$hControl = ControlGetHandle($TARGET_TITLE, "", "WindowsForms10.EDIT.app.0.141b42a_r8_ad12")
	ControlSetText($TARGET_TITLE, "", $hControl, "")
	Sleep(1000)
	ControlSend($TARGET_TITLE,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad12","1 2 3 4")
	;点击Write
	$hControl = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad15")
	ControlClick($TARGET_TITLE,"",$hControl)
	;确认 弹窗
	Send("{ENTER}")
	Sleep(1000)
	;点击Search
	$hControl = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad14")
	ControlClick($TARGET_TITLE,"",$hControl)
	;输入需要开启的 COM
	ControlClick($TARGET_TITLE,"","WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad12")
	Sleep(1000)
	$hControl = ControlGetHandle($TARGET_TITLE, "", "WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad12")
	ControlSetText($TARGET_TITLE, "", $hControl, "")
	Sleep(1000)
	ControlSend($TARGET_TITLE,"","WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad12","COM10;COM11;COM12;COM9")
	ControlFocus($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
	ControlClick($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
	#comments-end
	; 等待connect button
	Local $hButton = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
	Local $hButtonText = ControlGetText($TARGET_TITLE,"",$hButton)
	If StringLower($hButtonText) = "DisConnect" Then
		Return
    EndIf
	Local $hButton = WaitForControlEx($TARGET_TITLE,"WindowsForms10.BUTTON.app.0.141b42a_r8_ad11")
	ControlFocus($TARGET_TITLE,"",$hButton)
	ControlClick($TARGET_TITLE,"",$hButton)
	Sleep(2000)
EndFunc

Func SetRf()
	Local $hControl = ControlGetHandle($TARGET_TITLE,"","WindowsForms10.EDIT.app.0.141b42a_r8_ad11")
	ControlSetText($TARGET_TITLE,"",$hControl,"")
	Sleep(1000)
	;输入需要开启的 COM
	ControlSend($TARGET_TITLE,"",$hControl,$param1)
	ControlFocus($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad12")
	ControlClick($TARGET_TITLE,"","WindowsForms10.BUTTON.app.0.141b42a_r8_ad12")
	Local $startTime = TimerInit()
	While True
		Local $currentText = ControlGetText($TARGET_TITLE, "", "WindowsForms10.RichEdit20W.app.0.141b42a_r8_ad11")
		Local $lines = StringSplit($currentText, @CRLF)
		Local $lastLine = ""
		Local $i =0
		For $i = UBound($lines) - 1 To 0 Step -1
			If $lines[$i] <> "" Then
				$lastLine = $lines[$i]
				ExitLoop
			EndIf
		Next
		; 检查是否包含目标信息
		If $lastLine = "Set Attenuation to " & $param1 & " success."  Then
			MsgBox(0, "Success", "目标信息已找到：" & $lastLine,1)
			ExitLoop
		EndIf

		; 检查是否超时
		If TimerDiff($startTime) >= 5 * 1000 Then
			MsgBox(16, "Error", "等待超时，未找到目标信息。",1)
			Exit(1)
		EndIf

		Sleep(500)
	WEnd
EndFunc

; ============= 主程序开始 =============

; 检查命令行参数（允许1个数字或4个参数）

If $CmdLine[0] <> 1 And $CmdLine[0] <> 4 Then
    ShowError("参数错误", _
        "请提供以下两种参数格式之一：" & @CRLF & _
        "1. 单个数字参数" & @CRLF & _
        "2. 四个参数")
    Exit(1)
EndIf


; 参数处理
Global $param1, $param2, $param3, $param4

If $CmdLine[0] = 1 Then
    ; 单数字参数模式
    If Not StringIsDigit($CmdLine[1]) Then
        ShowError("参数类型错误", "单参数必须为数字")
        Exit(2)
    EndIf
    $param1 = Number($CmdLine[1])
Else
    ; 四参数模式
    $param1 = $CmdLine[1]
    $param2 = $CmdLine[2]
    $param3 = $CmdLine[3]
    $param4 = $CmdLine[4]
EndIf

; 处理ACUControlTool程序
HandleACUControlTool()
Init()
SetRf()
Exit(0) ; 正常退出
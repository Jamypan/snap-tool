# -*- coding: utf-8 -*-
"""界面文案的 8 语言对照表（i18n 的数据层）。

约定：
  * key 一律用「简体中文原文」，源码里 tr("中文") 即可，改动最小；
  * 值是 8 元组，顺序必须与 LANGS 一致，缺失/空串会回退到简体中文；
  * 带 {name} 之类占位符的句子，8 种语言必须使用同名占位符，
    selftest_editor.py 的 Stage O 会逐条校验。
"""
from __future__ import annotations

# 简体中文 / 繁體中文 / English / 日本語 / 한국어 / Français / Deutsch / Español
LANGS = ("zh_CN", "zh_TW", "en", "ja", "ko", "fr", "de", "es")

# 语言在设置对话框里显示的名字：本地名 + 英文名（避免用户看不懂）
LANGUAGE_NAMES = {
    "zh_CN": ("简体中文", "Chinese (Simplified)"),
    "zh_TW": ("繁體中文", "Chinese (Traditional)"),
    "en": ("English", "English"),
    "ja": ("日本語", "Japanese"),
    "ko": ("한국어", "Korean"),
    "fr": ("Français", "French"),
    "de": ("Deutsch", "German"),
    "es": ("Español", "Spanish"),
}

_ROWS: dict[str, tuple[str, ...]] = {
    # ------------------------------------------------------------ 通用
    "截屏助手": (
        "截屏助手", "截圖助手", "SnapTool", "スクリーンショット",
        "스크린샷 도우미", "Capture d'écran", "Bildschirmfoto", "Captura de pantalla",
    ),
    "确定": ("确定", "確定", "OK", "OK", "확인", "OK", "OK", "Aceptar"),
    "取消": ("取消", "取消", "Cancel", "キャンセル", "취소", "Annuler", "Abbrechen", "Cancelar"),
    "关闭": ("关闭", "關閉", "Close", "閉じる", "닫기", "Fermer", "Schließen", "Cerrar"),
    "保存": ("保存", "儲存", "Save", "保存", "저장", "Enregistrer", "Speichern", "Guardar"),
    "复制": ("复制", "複製", "Copy", "コピー", "복사", "Copier", "Kopieren", "Copiar"),
    "退出": ("退出", "結束", "Exit", "終了", "종료", "Quitter", "Beenden", "Salir"),
    "返回": ("返回", "返回", "Back", "戻る", "돌아가기", "Retour", "Zurück", "Volver"),
    "更改…": ("更改…", "變更…", "Change…", "変更…", "변경…", "Modifier…", "Ändern…", "Cambiar…"),
    "关于…": ("关于…", "關於…", "About…", "情報…", "정보…", "À propos…", "Über…", "Acerca de…"),
    # 「关于」窗口版本号标签（占位符 8 语言必须同名，Stage O 会校验）
    "版本：{version}": (
        "版本：{version}", "版本：{version}", "Version: {version}",
        "バージョン: {version}", "버전: {version}", "Version : {version}",
        "Version: {version}", "Versión: {version}",
    ),
    "使用说明…": ("使用说明…", "使用說明…", "User Guide…", "使い方…", "사용 설명서…", "Guide…", "Handbuch…", "Guía…"),
    "命令行参数…": ("命令行参数…", "命令列參數…", "Command Line…", "コマンドライン…", "명령줄 옵션…", "Ligne de commande…", "Befehlszeile…", "Línea de comandos…"),
    "设置热键…": ("设置热键…", "設定熱鍵…", "Set Hotkey…", "ショートカット設定…", "단축키 설정…", "Raccourci…", "Tastenkürzel…", "Atajo de teclado…"),
    # v34 贴图钉在桌面
    "钉在桌面": ("钉在桌面", "釘在桌面", "Pin to Desktop", "デスクトップにピン留め", "데스크톱에 고정", "Épingler au bureau", "Auf Desktop anheften", "Fijar al escritorio"),
    "钉在桌面：把当前截图贴成可移动的浮窗": (
        "钉在桌面：把当前截图贴成可移动的浮窗", "釘在桌面：把目前截圖貼成可移動的浮窗",
        "Pin to Desktop: paste the current capture as a movable overlay",
        "デスクトップにピン留め：現在のキャプチャを移動可能な浮遊ウィンドウにします",
        "데스크톱에 고정: 현재 캡처를 이동 가능한 플로팅 창으로 붙입니다",
        "Épingler au bureau : coller la capture actuelle comme un volet mobile",
        "Auf Desktop anheften: aktuellen Screenshot als verschiebbares Fenster anzeigen",
        "Fijar al escritorio: pegar la captura actual como una ventana flotante",
    ),
    "贴图": ("贴图", "貼圖", "Pinned Image", "ピン留め画像", "고정 이미지", "Image épinglée", "Angeheftetes Bild", "Imagen fijada"),
    "贴出剪贴板图片": ("贴出剪贴板图片", "貼出剪貼簿圖片", "Paste Clipboard Image", "クリップボード画像を貼り付け", "클립보드 이미지 붙여넣기", "Coller l'image du presse-papiers", "Zwischenablagebild einfügen", "Pegar imagen del portapapeles"),
    "贴出剪贴板图片  {label}": (
        "贴出剪贴板图片  {label}", "貼出剪貼簿圖片  {label}", "Paste Clipboard Image  {label}",
        "クリップボード画像を貼り付け  {label}", "클립보드 이미지 붙여넣기  {label}",
        "Coller l'image du presse-papiers  {label}", "Zwischenablagebild einfügen  {label}",
        "Pegar imagen del portapapeles  {label}",
    ),
    "设置贴图热键…": ("设置贴图热键…", "設定貼圖熱鍵…", "Set Pin Hotkey…", "貼り付け熱鍵の設定…", "고정 단축키 설정…", "Raccourci d'épinglage…", "Pin-Tastenkürzel…", "Atajo de fijar…"),
    "设置贴图热键 - {app}": (
        "设置贴图热键 - {app}", "設定貼圖熱鍵 - {app}", "Set Pin Hotkey - {app}",
        "貼り付け熱鍵の設定 - {app}", "고정 단축키 설정 - {app}",
        "Raccourci d'épinglage - {app}", "Pin-Tastenkürzel - {app}",
        "Atajo de fijar - {app}",
    ),
    "贴图热键已改为 {label}": (
        "贴图热键已改为 {label}", "貼圖熱鍵已改為 {label}", "Pin hotkey changed to {label}",
        "貼り付け熱鍵を {label} に変更しました", "고정 단축키가 {label}(으)로 변경되었습니다",
        "Raccourci d'épinglage changé pour {label}", "Pin-Tastenkürzel geändert zu {label}",
        "Atajo de fijar cambiado a {label}",
    ),
    "已把截图钉在桌面  {w}×{h}": (
        "已把截图钉在桌面  {w}×{h}", "已把截圖釘在桌面  {w}×{h}",
        "Pinned capture to desktop  {w}×{h}", "キャプチャをデスクトップにピン留めしました  {w}×{h}",
        "캡처를 데스크톱에 고정했습니다  {w}×{h}", "Capture épinglée au bureau  {w}×{h}",
        "Screenshot auf Desktop angeheftet  {w}×{h}", "Captura fijada al escritorio  {w}×{h}",
    ),
    "已把剪贴板图片钉在桌面  {w}×{h}": (
        "已把剪贴板图片钉在桌面  {w}×{h}", "已把剪貼簿圖片釘在桌面  {w}×{h}",
        "Pinned clipboard image to desktop  {w}×{h}", "クリップボード画像をデスクトップにピン留めしました  {w}×{h}",
        "클립보드 이미지를 데스크톱에 고정했습니다  {w}×{h}", "Image du presse-papiers épinglée au bureau  {w}×{h}",
        "Zwischenablagebild auf Desktop angeheftet  {w}×{h}", "Imagen del portapapeles fijada al escritorio  {w}×{h}",
    ),
    "剪贴板里没有图片，无法贴图。": (
        "剪贴板里没有图片，无法贴图。", "剪貼簿裡沒有圖片，無法貼圖。",
        "No image in the clipboard; nothing to pin.",
        "クリップボードに画像がないため、貼り付けできません。",
        "클립보드에 이미지가 없어 붙여넣을 수 없습니다.",
        "Aucune image dans le presse-papiers ; rien à épingler.",
        "Kein Bild in der Zwischenablage – nichts anzuheften.",
        "No hay imagen en el portapapeles; no se puede fijar.",
    ),
    "复制图片": ("复制图片", "複製圖片", "Copy Image", "画像をコピー", "이미지 복사", "Copier l'image", "Bild kopieren", "Copiar imagen"),
    "另存为…": ("另存为…", "另存為…", "Save As…", "名前を付けて保存…", "다른 이름으로 저장…", "Enregistrer sous…", "Speichern unter…", "Guardar como…"),
    "透明度": ("透明度", "透明度", "Opacity", "不透明度", "불투명도", "Opacité", "Deckkraft", "Opacidad"),
    "保持置顶": ("保持置顶", "保持置頂", "Keep on Top", "常に最前面", "항상 위에", "Toujours au-dessus", "Immer oben", "Siempre encima"),
    "重置大小": ("重置大小", "重設大小", "Reset Size", "サイズをリセット", "크기 재설정", "Réinitialiser la taille", "Größe zurücksetzen", "Restablecer tamaño"),
    "关闭贴图": ("关闭贴图", "關閉貼圖", "Close Pin", "ピン留めを閉じる", "고정 닫기", "Fermer l'épinglage", "Anheftung schließen", "Cerrar fijación"),
    "保存贴图": ("保存贴图", "儲存貼圖", "Save Pinned Image", "ピン留め画像を保存", "고정 이미지 저장", "Enregistrer l'image épinglée", "Angeheftetes Bild speichern", "Guardar imagen fijada"),
    "贴图用法": (
        "把当前截图（含标注）贴成一张<b>无边框、可置顶的图片浮窗</b>，像便利贴一样钉在桌面。"
        "四个入口：框选后的「钉在桌面」按钮、编辑器「文件 → 钉在桌面」、"
        "托盘「贴出剪贴板图片」、贴图热键（默认 Ctrl + Shift + P，可在设置中修改）。",
        "把目前截圖（含標註）貼成一張<b>無邊框、可置頂的圖片浮窗</b>，像便利貼一樣釘在桌面。"
        "四個入口：框選後的「釘在桌面」按鈕、編輯器「檔案 → 釘在桌面」、"
        "系統匣「貼出剪貼簿圖片」、貼圖熱鍵（預設 Ctrl + Shift + P，可在設定中修改）。",
        "Pins the current capture (with annotations) as a <b>borderless, always-on-top image overlay</b>, "
        "like a sticky note on your desktop. Four entry points: the Pin to Desktop button after selecting, "
        "Editor → File → Pin to Desktop, the tray's Paste Clipboard Image, and the pin hotkey "
        "(default Ctrl + Shift + P, configurable in Settings).",
        "現在のキャプチャ（注釈を含む）を<b>枠なし・最前面表示の画像浮遊ウィンドウ</b>として貼り付け、"
        "付箋のようにデスクトップに留めます。4 つの入口：範囲選択後の「ピン留め」ボタン、"
        "エディターの「ファイル → ピン留め」、トレイの「クリップボード画像を貼り付け」、"
        "ピン留め熱鍵（既定 Ctrl + Shift + P、設定で変更可）。",
        "현재 캡처(주석 포함)를 <b>테두리 없는 항상 위 이미지 창</b>으로 붙여 메모처럼 데스크톱에 고정합니다. "
        "네 가지 진입점: 영역 선택 후 '데스크톱에 고정' 버튼, 편집기 '파일 → 데스크톱에 고정', "
        "트레이 '클립보드 이미지 붙여넣기', 고정 단축키(기본 Ctrl+Shift+P, 설정에서 변경 가능).",
        "Épingle la capture actuelle (avec annotations) comme un <b>volet d'image sans bordure, toujours au-dessus</b>, "
        "tel un pense-bête sur le bureau. Quatre entrées : le bouton Épingler après sélection, "
        "Éditeur → Fichier → Épingler, le menu Coller l'image du presse-papiers, et le raccourci d'épinglage "
        "(par défaut Ctrl + Maj + P, modifiable dans les paramètres).",
        "Hält den aktuellen Screenshot (mit Anmerkungen) als <b>rahmenloses, immer oben liegendes Bildfenster</b> "
        "wie einen Haftzettel auf dem Desktop fest. Vier Zugänge: die Schaltfläche „Auf Desktop anheften“ nach der "
        "Auswahl, Editor → Datei → Auf Desktop anheften, das Tray-Menü „Zwischenablagebild einfügen“ und die "
        "Pin-Taste (Standard Strg+Umschalt+P, in den Einstellungen änderbar).",
        "Fija la captura actual (con anotaciones) como una <b>ventana de imagen flotante sin borde y siempre encima</b>, "
        "como una nota adhesiva en el escritorio. Cuatro entradas: el botón Fijar al escritorio tras seleccionar, "
        "Editor → Archivo → Fijar al escritorio, el menú Pegar imagen del portapapeles y el atajo de fijar "
        "(predeterminado Ctrl+Mayús+P, configurable en Ajustes).",
    ),
    "贴图操作": (
        "浮窗操作：<b>左键拖动</b>移动，<b>滚轮</b>缩放（0.1~8 倍），<b>右键菜单</b>可复制图片 / 另存为 / "
        "调透明度（100/75/50/25%）/ 开关保持置顶 / 重置大小 / 关闭；<b>双击</b>或 <b>Esc</b> 关闭，"
        "<b>Ctrl+C</b> 复制原图。可同时钉多张，鼠标悬停时右上角出现关闭按钮。",
        "浮窗操作：<b>左鍵拖動</b>移動，<b>滾輪</b>縮放（0.1~8 倍），<b>右鍵選單</b>可複製圖片 / 另存為 / "
        "調整透明度（100/75/50/25%）/ 開關保持置頂 / 重設大小 / 關閉；<b>雙擊</b>或 <b>Esc</b> 關閉，"
        "<b>Ctrl+C</b> 複製原圖。可同時釘多張，滑鼠懸停時右上角出現關閉按鈕。",
        "Overlay controls: <b>left-drag</b> to move, <b>mouse wheel</b> to zoom (0.1–8x), <b>right-click menu</b> "
        "to copy / save as / set opacity (100/75/50/25%) / toggle keep-on-top / reset size / close; "
        "<b>double-click</b> or <b>Esc</b> to close, <b>Ctrl+C</b> to copy the original. Multiple pins are allowed; "
        "hover to reveal a close button in the top-right corner.",
        "浮遊ウィンドウの操作：<b>左ドラッグ</b>で移動、<b>ホイール</b>で拡大縮小（0.1〜8 倍）、"
        "<b>右クリックメニュー</b>で画像コピー / 名前を付けて保存 / 不透明度変更（100/75/50/25%）/ "
        "常に最前面の切替 / サイズリセット / 閉じる；<b>ダブルクリック</b>または <b>Esc</b> で閉じ、"
        "<b>Ctrl+C</b> で元画像をコピー。複数同時に留められ、カーソルを合わせると右上に閉じるボタンが表示されます。",
        "플로팅 창 조작: <b>왼쪽 드래그</b>로 이동, <b>휠</b>로 확대/축소(0.1~8배), <b>오른쪽 클릭 메뉴</b>에서 "
        "이미지 복사 / 다른 이름으로 저장 / 불투명도 조절(100/75/50/25%) / 항상 위 켜기·끄기 / 크기 재설정 / 닫기; "
        "<b>더블클릭</b> 또는 <b>Esc</b>로 닫고, <b>Ctrl+C</b>로 원본 복사. 여러 개를 동시에 고정할 수 있고, "
        "마우스를 올리면 오른쪽 위에 닫기 버튼이 나타납니다.",
        "Contrôles du volet : <b>glisser à gauche</b> pour déplacer, <b>molette</b> pour zoomer (0,1–8x), "
        "<b>menu contextuel</b> pour copier / enregistrer / régler l'opacité (100/75/50/25%) / basculer "
        "« toujours au-dessus » / réinitialiser la taille / fermer ; <b>double-clic</b> ou <b>Échap</b> pour fermer, "
        "<b>Ctrl+C</b> pour copier l'original. Plusieurs épingles sont possibles ; survolez pour afficher le bouton de fermeture en haut à droite.",
        "Steuerung des Fensters: <b>linksziehen</b> zum Verschieben, <b>Mausrad</b> zum Zoomen (0,1–8x), "
        "<b>Rechtsklick-Menü</b> zum Kopieren / Speichern / Deckkraft ändern (100/75/50/25%) / Immer-oben umschalten / "
        "Größe zurücksetzen / Schließen; <b>Doppelklick</b> oder <b>Esc</b> zum Schließen, <b>Strg+C</b> kopiert das Original. "
        "Mehrere Pins sind möglich; beim Überfahren erscheint oben rechts eine Schaltfläche zum Schließen.",
        "Controles de la ventana: <b>arrastrar con el botón izquierdo</b> para mover, <b>rueda del ratón</b> para ampliar "
        "(0,1–8x), <b>menú contextual</b> para copiar / guardar como / ajustar opacidad (100/75/50/25%) / activar o "
        "desactivar «siempre encima» / restablecer tamaño / cerrar; <b>doble clic</b> o <b>Esc</b> para cerrar, "
        "<b>Ctrl+C</b> para copiar la imagen original. Se pueden fijar varias; al pasar el ratón aparece un botón de cierre arriba a la derecha.",
    ),
    "语言…": ("语言…", "語言…", "Language…", "言語…", "언어…", "Langue…", "Sprache…", "Idioma…"),
    "使用说明": ("使用说明", "使用說明", "User Guide", "使い方", "사용 설명서", "Guide d'utilisation", "Handbuch", "Guía de uso"),
    "命令行参数": ("命令行参数", "命令列參數", "Command Line", "コマンドライン", "명령줄 옵션", "Ligne de commande", "Befehlszeile", "Línea de comandos"),
    "语言": ("语言", "語言", "Language", "言語", "언어", "Langue", "Sprache", "Idioma"),
    "未知": ("未知", "未知", "Unknown", "不明", "알 수 없음", "Inconnu", "Unbekannt", "Desconocido"),
    "框选截图": ("框选截图", "框選截圖", "Area Capture", "範囲キャプチャ", "영역 캡처", "Capture de zone", "Bereichsaufnahme", "Captura de área"),
    "窗口截图": ("窗口截图", "視窗截圖", "Window Capture", "ウィンドウキャプチャ", "창 캡처", "Capture de fenêtre", "Fensteraufnahme", "Captura de ventana"),
    "全屏截图": ("全屏截图", "全螢幕截圖", "Full Screen", "全画面キャプチャ", "전체 화면", "Plein écran", "Vollbild", "Pantalla completa"),
    "拖动鼠标框选任意区域": (
        "拖动鼠标框选任意区域", "拖曳滑鼠框選任意區域", "Drag to select any area",
        "ドラッグして範囲を選択", "드래그하여 영역 선택", "Glisser pour sélectionner",
        "Ziehen zum Auswählen", "Arrastrar para seleccionar",
    ),
    "移动鼠标点选一个窗口": (
        "移动鼠标点选一个窗口", "移動滑鼠點選一個視窗", "Hover over a window and click",
        "ウィンドウにカーソルを合わせてクリック", "창 위로 마우스를 옮기고 클릭",
        "Survoler une fenêtre et cliquer", "Fenster unter dem Zeiger anklicken",
        "Sitúese sobre una ventana y haga clic",
    ),
    "整个屏幕（含多显示器）": (
        "整个屏幕（含多显示器）", "整個螢幕（含多顯示器）", "Entire screen (all monitors)",
        "画面全体（複数モニター含む）", "전체 화면(멀티 모니터 포함)",
        "Tout l'écran (multi-moniteurs)", "Gesamter Bildschirm (alle Monitore)",
        "Pantalla completa (varios monitores)",
    ),

    # ------------------------------------------------------------ 主窗口
    "文件(&F)": ("文件(&F)", "檔案(&F)", "File(&F)", "ファイル(&F)", "파일(&F)", "Fichier(&F)", "Datei(&F)", "Archivo(&F)"),
    "打开保存目录": ("打开保存目录", "開啟儲存目錄", "Open Save Folder", "保存フォルダーを開く", "저장 폴더 열기", "Ouvrir le dossier", "Speicherordner öffnen", "Abrir carpeta"),
    "最小化到托盘": ("最小化到托盘", "最小化到系統匣", "Minimize to Tray", "トレイに最小化", "트레이로 최소화", "Réduire dans la barre", "In die Taskleiste minimieren", "Minimizar a la bandeja"),
    "截图(&S)": ("截图(&S)", "截圖(&S)", "Capture(&S)", "キャプチャ(&S)", "캡처(&S)", "Capture(&S)", "Aufnahme(&S)", "Captura(&S)"),
    "设置(&E)": ("设置(&E)", "設定(&E)", "Settings(&E)", "設定(&E)", "설정(&E)", "Paramètres(&E)", "Einstellungen(&E)", "Ajustes(&E)"),
    "帮助(&H)": ("帮助(&H)", "說明(&H)", "Help(&H)", "ヘルプ(&H)", "도움말(&H)", "Aide(&H)", "Hilfe(&H)", "Ayuda(&H)"),
    "程序已启动 · 托盘常驻 · 关闭本窗口只会最小化到托盘，不会退出程序": (
        "程序已启动 · 托盘常驻 · 关闭本窗口只会最小化到托盘，不会退出程序",
        "程式已啟動 · 常駐系統匣 · 關閉本視窗只會最小化，不會結束程式",
        "Running · Resident in tray · Closing this window only minimizes, the app keeps running",
        "起動中 · トレイ常駐 · ウィンドウを閉じても最小化するだけで終了しません",
        "실행 중 · 트레이 상주 · 창을 닫아도 최소화되며 프로그램은 종료되지 않습니다",
        "En cours · Présent dans la barre · Fermer cette fenêtre minimise seulement l'application",
        "Aktiv · Im Infobereich · Das Schließen minimiert nur, das Programm läuft weiter",
        "En ejecución · En la bandeja · Cerrar esta ventana solo minimiza, la app sigue activa",
    ),
    "截图热键": ("截图热键", "截圖熱鍵", "Capture Hotkey", "キャプチャのショートカット", "캡처 단축키", "Raccourci de capture", "Aufnahme-Tastenkürzel", "Atajo de captura"),
    "默认模式": ("默认模式", "預設模式", "Default Mode", "既定のモード", "기본 모드", "Mode par défaut", "Standardmodus", "Modo predeterminado"),
    "画笔平滑度": ("画笔平滑度", "畫筆平滑度", "Pen Smoothness", "ペンの平滑化", "펜 부드럽기", "Lissage du crayon", "Stiftglättung", "Suavidad del lápiz"),
    "关闭（原始线条）": ("关闭（原始线条）", "關閉（原始線條）", "Off (raw lines)", "オフ（元の線）", "끄기 (원래 선)", "Désactivé (lignes brutes)", "Aus (ursprüngliche Linien)", "Desactivado (líneas originales)"),
    "轻度": ("轻度", "輕度", "Light", "軽度", "약함", "Léger", "Leicht", "Suave"),
    "中等": ("中等", "中等", "Medium", "中程度", "보통", "Moyen", "Mittel", "Medio"),
    "强": ("强", "強", "Strong", "強", "강함", "Fort", "Stark", "Fuerte"),
    "热键与托盘「截图」使用此模式": (
        "热键与托盘「截图」使用此模式", "熱鍵與系統匣「截圖」使用此模式",
        "Used by the hotkey and tray capture", "ショートカットとトレイのキャプチャで使用",
        "단축키와 트레이 캡처에 사용됩니다", "Utilisé par le raccourci et la capture de la barre",
        "Wird für Tastenkürzel und Tray-Aufnahme genutzt", "Usado por el atajo y la captura de la bandeja",
    ),
    "立即截图": ("立即截图", "立即截圖", "Capture Now", "今すぐキャプチャ", "지금 캡처", "Capturer maintenant", "Jetzt aufnehmen", "Capturar ahora"),
    "提示：截图中按 Esc 取消；选区确定后可标注、取字、复制或保存。 详细说明见「帮助 → 使用说明」。": (
        "提示：截图中按 Esc 取消；选区确定后可标注、取字、复制或保存。 详细说明见「帮助 → 使用说明」。",
        "提示：截圖時按 Esc 取消；選區確認後可標註、取字、複製或儲存。 詳細說明見「說明 → 使用說明」。",
        "Tip: press Esc to cancel; after confirming the selection you can annotate, extract text, copy or save. See Help → User Guide.",
        "ヒント：Esc でキャンセル。範囲確定後は注釈・文字認識・コピー・保存ができます。詳しくは ヘルプ → 使い方。",
        "팁: Esc로 취소; 영역 확정 후 주석, 문자 인식, 복사, 저장이 가능합니다. 도움말 → 사용 설명서 참조.",
        "Astuce : Esc pour annuler ; après validation, annotez, extrayez le texte, copiez ou enregistrez. Voir Aide → Guide.",
        "Tipp: Esc bricht ab; nach Bestätigung können Sie markieren, Text erkennen, kopieren oder speichern. Siehe Hilfe → Handbuch.",
        "Consejo: Esc cancela; tras confirmar puede anotar, extraer texto, copiar o guardar. Vea Ayuda → Guía.",
    ),
    "保存目录：{path}": (
        "保存目录：{path}", "儲存目錄：{path}", "Save folder: {path}",
        "保存フォルダー: {path}", "저장 폴더: {path}", "Dossier : {path}",
        "Speicherordner: {path}", "Carpeta: {path}",
    ),
    "{app} - 使用说明": (
        "{app} - 使用说明", "{app} - 使用說明", "{app} - User Guide", "{app} - 使い方",
        "{app} - 사용 설명서", "{app} - Guide", "{app} - Handbuch", "{app} - Guía",
    ),
    "{app} - 命令行参数": (
        "{app} - 命令行参数", "{app} - 命令列參數", "{app} - Command Line",
        "{app} - コマンドライン", "{app} - 명령줄 옵션", "{app} - Ligne de commande",
        "{app} - Befehlszeile", "{app} - Línea de comandos",
    ),
    "关于 {app}": ("关于 {app}", "關於 {app}", "About {app}", "{app} について", "{app} 정보", "À propos de {app}", "Über {app}", "Acerca de {app}"),
    "{app} - 截图编辑": (
        "{app} - 截图编辑", "{app} - 截圖編輯", "{app} - Image Editor", "{app} - 画像編集",
        "{app} - 이미지 편집", "{app} - Édition d'image", "{app} - Bildbearbeitung", "{app} - Editor de imagen",
    ),
    "{app} - 长截图预览": (
        "{app} - 长截图预览", "{app} - 長截圖預覽", "{app} - Scrolling Capture Preview",
        "{app} - スクロールキャプチャ プレビュー", "{app} - 스크롤 캡처 미리보기",
        "{app} - Aperçu de la capture défilante", "{app} - Vorschau der Scroll-Aufnahme", "{app} - Vista previa de captura larga",
    ),
    "{app} - 已复制到剪贴板": (
        "{app} - 已复制到剪贴板", "{app} - 已複製到剪貼簿", "{app} - Copied to Clipboard",
        "{app} - クリップボードにコピー", "{app} - 클립보드에 복사됨", "{app} - Copié dans le presse-papiers",
        "{app} - In die Zwischenablage kopiert", "{app} - Copiado al portapapeles",
    ),
    "{app} - 已保存：{path}": (
        "{app} - 已保存：{path}", "{app} - 已儲存：{path}", "{app} - Saved: {path}",
        "{app} - 保存しました: {path}", "{app} - 저장됨: {path}", "{app} - Enregistré : {path}",
        "{app} - Gespeichert: {path}", "{app} - Guardado: {path}",
    ),
    "{app} - 命令行说明": (
        "{app} - 命令行说明", "{app} - 命令列說明", "{app} - Command Line Help",
        "{app} - コマンドラインの説明", "{app} - 명령줄 도움말", "{app} - Aide sur la ligne de commande",
        "{app} - Befehlszeilenhilfe", "{app} - Ayuda de línea de comandos",
    ),

    # ------------------------------------------------------------ 语言设置
    "界面语言": ("界面语言", "介面語言", "Interface Language", "表示言語", "인터페이스 언어", "Langue de l'interface", "Oberflächensprache", "Idioma de la interfaz"),
    "语言设置": ("语言设置", "語言設定", "Language Settings", "言語設定", "언어 설정", "Paramètres de langue", "Spracheinstellungen", "Configuración de idioma"),
    "跟随系统": ("跟随系统", "跟隨系統", "Follow System", "システム設定に従う", "시스템 설정 따르기", "Suivre le système", "Systemeinstellung folgen", "Seguir el sistema"),
    "跟随系统（{name}）": (
        "跟随系统（{name}）", "跟隨系統（{name}）", "Follow System ({name})",
        "システム設定に従う（{name}）", "시스템 설정 따르기 ({name})",
        "Suivre le système ({name})", "Systemeinstellung folgen ({name})", "Seguir el sistema ({name})",
    ),
    "选择程序界面使用的语言。启动时默认跟随系统语言，设置会被记住。": (
        "选择程序界面使用的语言。启动时默认跟随系统语言，设置会被记住。",
        "選擇程式介面使用的語言。啟動時預設跟隨系統語言，設定會被記住。",
        "Choose the interface language. By default the app follows your system language at startup; your choice is remembered.",
        "画面の表示言語を選択します。起動時は既定でシステム言語に従い、設定は記憶されます。",
        "인터페이스 언어를 선택하세요. 기본값은 시작 시 시스템 언어를 따르며 설정은 저장됩니다.",
        "Choisissez la langue de l'interface. Par défaut, l'application suit la langue du système au démarrage ; le choix est mémorisé.",
        "Sprache der Oberfläche wählen. Standardmäßig folgt die App beim Start der Systemsprache; die Auswahl wird gespeichert.",
        "Elija el idioma de la interfaz. Por defecto la app sigue el idioma del sistema al iniciar; se recuerda su elección.",
    ),
    "当前语言：{name}": (
        "当前语言：{name}", "目前語言：{name}", "Current language: {name}",
        "現在の言語: {name}", "현재 언어: {name}", "Langue actuelle : {name}",
        "Aktuelle Sprache: {name}", "Idioma actual: {name}",
    ),
    "切换后已打开的窗口会立即刷新。": (
        "切换后已打开的窗口会立即刷新。", "切換後已開啟的視窗會立即更新。",
        "Open windows refresh immediately.", "開いているウィンドウはすぐに更新されます。",
        "열려 있는 창은 즉시 갱신됩니다.", "Les fenêtres ouvertes se mettent à jour immédiatement.",
        "Geöffnete Fenster werden sofort aktualisiert.", "Las ventanas abiertas se actualizan al instante.",
    ),

    # ------------------------------------------------------------ 托盘 / 通知
    "显示主窗口": ("显示主窗口", "顯示主視窗", "Show Main Window", "メインウィンドウを表示", "주 창 표시", "Afficher la fenêtre principale", "Hauptfenster anzeigen", "Mostrar ventana principal"),
    "截图": ("截图", "截圖", "Capture", "キャプチャ", "캡처", "Capture", "Aufnehmen", "Capturar"),
    "截图  {label}": ("截图  {label}", "截圖  {label}", "Capture  {label}", "キャプチャ  {label}", "캡처  {label}", "Capture  {label}", "Aufnehmen  {label}", "Capturar  {label}"),
    "{app}（{label} 截图 · 右键可改热键）": (
        "{app}（{label} 截图 · 右键可改热键）", "{app}（{label} 截圖 · 右鍵可改熱鍵）",
        "{app} ({label} to capture · right-click to change hotkey)",
        "{app}（{label} でキャプチャ · 右クリックでショートカット変更）",
        "{app} ({label} 캡처 · 오른쪽 클릭으로 단축키 변경)",
        "{app} ({label} pour capturer · clic droit pour le raccourci)",
        "{app} ({label} zum Aufnehmen · Rechtsklick für Tastenkürzel)",
        "{app} ({label} para capturar · clic derecho para el atajo)",
    ),
    "程序本来就在运行，已为你显示主窗口。": (
        "程序本来就在运行，已为你显示主窗口。", "程式本來就在執行，已為你顯示主視窗。",
        "The app was already running; its main window is now shown.",
        "アプリは既に起動中です。メインウィンドウを表示しました。",
        "이미 실행 중입니다. 주 창을 표시했습니다.",
        "L'application était déjà en cours ; la fenêtre principale est affichée.",
        "Die App lief bereits; das Hauptfenster wurde angezeigt.",
        "La app ya estaba en ejecución; se mostró la ventana principal.",
    ),
    "已最小化到托盘，程序仍在运行。右键托盘可重新打开主窗口或退出。": (
        "已最小化到托盘，程序仍在运行。右键托盘可重新打开主窗口或退出。",
        "已最小化到系統匣，程式仍在執行。右鍵系統匣可重新開啟主視窗或結束。",
        "Minimized to tray; the app is still running. Right-click the tray icon to reopen or exit.",
        "トレイに最小化しました。アプリは実行中です。トレイアイコンを右クリックで再表示または終了できます。",
        "트레이로 최소화되었습니다. 프로그램은 계속 실행 중입니다. 트레이 아이콘을 오른쪽 클릭하면 다시 열거나 종료할 수 있습니다.",
        "Réduite dans la barre ; l'application reste active. Clic droit sur l'icône pour rouvrir ou quitter.",
        "In den Infobereich minimiert; die App läuft weiter. Rechtsklick auf das Symbol zum Öffnen oder Beenden.",
        "Minimizada a la bandeja; la app sigue activa. Clic derecho en el icono para abrir o salir.",
    ),
    "默认截图模式已设为「{mode}」，热键与托盘截图将使用此模式": (
        "默认截图模式已设为「{mode}」，热键与托盘截图将使用此模式",
        "預設截圖模式已設為「{mode}」，熱鍵與系統匣截圖將使用此模式",
        "Default capture mode set to {mode}; hotkey and tray capture will use it",
        "既定のキャプチャ モードを {mode} に設定しました。ショートカットとトレイでも使用されます",
        "기본 캡처 모드가 {mode}(으)로 설정되었습니다. 단축키와 트레이 캡처에 적용됩니다",
        "Mode de capture par défaut : {mode} ; utilisé par le raccourci et la barre",
        "Standard-Aufnahmemodus: {mode}; gilt für Tastenkürzel und Tray",
        "Modo de captura predeterminado: {mode}; lo usarán el atajo y la bandeja",
    ),
    "（配置写入失败，重启后会恢复）": (
        "（配置写入失败，重启后会恢复）", "（設定寫入失敗，重啟後會還原）",
        " (settings could not be saved; will revert after restart)",
        "（設定を保存できませんでした。再起動後に戻ります）",
        " (설정을 저장하지 못했습니다. 재시작 후 복원됩니다)",
        " (enregistrement impossible ; valeur restaurée au redémarrage)",
        " (Einstellungen konnten nicht gespeichert werden; nach Neustart zurückgesetzt)",
        " (no se pudo guardar; se restaurará al reiniciar)",
    ),
    "截屏失败：{error}": (
        "截屏失败：{error}", "截圖失敗：{error}", "Capture failed: {error}",
        "キャプチャに失敗しました: {error}", "캡처 실패: {error}", "Échec de la capture : {error}",
        "Aufnahme fehlgeschlagen: {error}", "Error de captura: {error}",
    ),
    "保存失败：{path}": (
        "保存失败：{path}", "儲存失敗：{path}", "Save failed: {path}",
        "保存に失敗しました: {path}", "저장 실패: {path}", "Échec de l'enregistrement : {path}",
        "Speichern fehlgeschlagen: {path}", "Error al guardar: {path}",
    ),
    "已复制到剪贴板  {w}×{h}": (
        "已复制到剪贴板  {w}×{h}", "已複製到剪貼簿  {w}×{h}", "Copied to clipboard  {w}×{h}",
        "クリップボードにコピー  {w}×{h}", "클립보드에 복사됨  {w}×{h}",
        "Copié dans le presse-papiers  {w}×{h}", "In die Zwischenablage kopiert  {w}×{h}",
        "Copiado al portapapeles  {w}×{h}",
    ),
    "截图_": ("截图_", "截圖_", "Screenshot_", "Screenshot_", "Screenshot_", "Capture_", "Aufnahme_", "Captura_"),
    "长截图_": ("长截图_", "長截圖_", "Longshot_", "Longshot_", "Longshot_", "Capture_longue_", "Scrollaufnahme_", "Captura_larga_"),
    "PNG 图片 (*.png);;JPEG 图片 (*.jpg)": (
        "PNG 图片 (*.png);;JPEG 图片 (*.jpg)", "PNG 圖片 (*.png);;JPEG 圖片 (*.jpg)",
        "PNG Image (*.png);;JPEG Image (*.jpg)", "PNG 画像 (*.png);;JPEG 画像 (*.jpg)",
        "PNG 이미지 (*.png);;JPEG 이미지 (*.jpg)", "Image PNG (*.png);;Image JPEG (*.jpg)",
        "PNG-Bild (*.png);;JPEG-Bild (*.jpg)", "Imagen PNG (*.png);;Imagen JPEG (*.jpg)",
    ),
    "保存截图": ("保存截图", "儲存截圖", "Save Screenshot", "スクリーンショットを保存", "스크린샷 저장", "Enregistrer la capture", "Aufnahme speichern", "Guardar captura"),
    "保存长截图": ("保存长截图", "儲存長截圖", "Save Long Capture", "長いキャプチャを保存", "스크롤 캡처 저장", "Enregistrer la capture longue", "Scroll-Aufnahme speichern", "Guardar captura larga"),
    "已保存：{path}": (
        "已保存：{path}", "已儲存：{path}", "Saved: {path}", "保存しました: {path}",
        "저장됨: {path}", "Enregistré : {path}", "Gespeichert: {path}", "Guardado: {path}",
    ),
    "内容未能自动对齐，结果可能不完整（页面可能有固定悬浮元素或动画）": (
        "内容未能自动对齐，结果可能不完整（页面可能有固定悬浮元素或动画）",
        "內容無法自動對齊，結果可能不完整（頁面可能有固定懸浮元素或動畫）",
        "Frames could not be aligned automatically; the result may be incomplete (fixed overlays or animations)",
        "フレームを自動整列できませんでした。結果が不完全な可能性があります（固定要素やアニメーション）",
        "프레임을 자동 정렬하지 못했습니다. 결과가 불완전할 수 있습니다(고정 요소 또는 애니메이션)",
        "Alignement automatique impossible ; le résultat peut être incomplet (éléments fixes ou animations)",
        "Automatische Ausrichtung fehlgeschlagen; Ergebnis evtl. unvollständig (fixe Elemente oder Animationen)",
        "No se pudo alinear automáticamente; el resultado puede estar incompleto (elementos fijos o animaciones)",
    ),
    "长截图失败：{error}": (
        "长截图失败：{error}", "長截圖失敗：{error}", "Scrolling capture failed: {error}",
        "スクロールキャプチャに失敗しました: {error}", "스크롤 캡처 실패: {error}",
        "Échec de la capture défilante : {error}", "Scroll-Aufnahme fehlgeschlagen: {error}",
        "Error de captura larga: {error}",
    ),
    "没有识别到文字。": (
        "没有识别到文字。", "沒有辨識到文字。", "No text recognized.",
        "文字が検出されませんでした。", "인식된 텍스트가 없습니다.", "Aucun texte reconnu.",
        "Kein Text erkannt.", "No se reconoció texto.",
    ),
    "OCR 不可用：{error}\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。": (
        "OCR 不可用：{error}\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。",
        "OCR 不可用：{error}\n\n請確認已安裝 OCR 依賴（rapidocr / onnxruntime）。",
        "OCR unavailable: {error}\n\nMake sure the OCR dependencies (rapidocr / onnxruntime) are installed.",
        "OCR を利用できません: {error}\n\nOCR 依存関係（rapidocr / onnxruntime）がインストールされているか確認してください。",
        "OCR을 사용할 수 없습니다: {error}\n\nOCR 종속성(rapidocr / onnxruntime)이 설치되었는지 확인하세요.",
        "OCR indisponible : {error}\n\nVérifiez que les dépendances OCR (rapidocr / onnxruntime) sont installées.",
        "OCR nicht verfügbar: {error}\n\nBitte OCR-Abhängigkeiten (rapidocr / onnxruntime) prüfen.",
        "OCR no disponible: {error}\n\nCompruebe que las dependencias OCR (rapidocr / onnxruntime) estén instaladas.",
    ),
    "正在滚动截屏…": (
        "正在滚动截屏…", "正在捲動截圖…", "Capturing scrolling page…",
        "スクロールキャプチャ中…", "스크롤 캡처 중…", "Capture défilante en cours…",
        "Scroll-Aufnahme läuft…", "Capturando página larga…",
    ),
    "已拼 {frames} 帧 · 当前高度 {height}px\n按 Esc 可随时结束": (
        "已拼 {frames} 帧 · 当前高度 {height}px\n按 Esc 可随时结束",
        "已拼 {frames} 幀 · 目前高度 {height}px\n按 Esc 可隨時結束",
        "{frames} frames stitched · height {height}px\nPress Esc to stop",
        "{frames} フレーム結合 · 高さ {height}px\nEsc で終了",
        "{frames}개 프레임 결합 · 높이 {height}px\nEsc로 종료",
        "{frames} images assemblées · hauteur {height}px\nEsc pour arrêter",
        "{frames} Bilder zusammengefügt · Höhe {height}px\nMit Esc beenden",
        "{frames} fotogramas unidos · alto {height}px\nEsc para detener",
    ),
    "尺寸：{w} × {h} px": (
        "尺寸：{w} × {h} px", "尺寸：{w} × {h} px", "Size: {w} × {h} px",
        "サイズ: {w} × {h} px", "크기: {w} × {h} px", "Taille : {w} × {h} px",
        "Größe: {w} × {h} px", "Tamaño: {w} × {h} px",
    ),
    "复制到剪贴板": (
        "复制到剪贴板", "複製到剪貼簿", "Copy to Clipboard", "クリップボードにコピー",
        "클립보드에 복사", "Copier dans le presse-papiers", "In die Zwischenablage kopieren", "Copiar al portapapeles",
    ),
    "保存为文件": (
        "保存为文件", "儲存為檔案", "Save as File", "ファイルに保存", "파일로 저장",
        "Enregistrer dans un fichier", "Als Datei speichern", "Guardar como archivo",
    ),
    "截图热键已改为 {label}": (
        "截图热键已改为 {label}", "截圖熱鍵已改為 {label}", "Capture hotkey changed to {label}",
        "キャプチャのショートカットを {label} に変更しました", "캡처 단축키가 {label}(으)로 변경되었습니다",
        "Raccourci de capture modifié : {label}", "Aufnahme-Tastenkürzel geändert: {label}",
        "Atajo de captura cambiado a {label}",
    ),
    "画笔平滑度已设为：{level}": (
        "画笔平滑度已设为：{level}", "畫筆平滑度已設為：{level}",
        "Pen smoothness set to: {level}", "ペンの平滑化を {level} に設定しました",
        "펜 부드럽기를 {level}(으)로 설정했습니다", "Lissage du crayon : {level}",
        "Stiftglättung: {level}", "Suavidad del lápiz: {level}",
    ),
    "（配置未能写入磁盘，重启后会恢复旧设置）": (
        "（配置未能写入磁盘，重启后会恢复旧设置）", "（設定未能寫入磁碟，重啟後會還原舊設定）",
        " (could not save settings; the old value returns after restart)",
        "（設定を保存できませんでした。再起動後に旧設定へ戻ります）",
        " (설정을 저장하지 못했습니다. 재시작 후 이전 설정으로 돌아갑니다)",
        " (enregistrement impossible ; ancienne valeur au redémarrage)",
        " (Einstellungen nicht gespeichert; alter Wert nach Neustart)",
        " (no se pudo guardar; se restaurará el valor anterior al reiniciar)",
    ),
    "{label} 无法注册：可能已被其他程序占用，或属于系统保留组合。请换一个。": (
        "{label} 无法注册：可能已被其他程序占用，或属于系统保留组合。请换一个。",
        "{label} 無法註冊：可能已被其他程式占用，或屬於系統保留組合。請換一個。",
        "{label} could not be registered: it may be in use by another app or reserved by the system. Try another.",
        "{label} を登録できませんでした。他のアプリが使用中かシステム予約の可能性があります。別の組み合わせを試してください。",
        "{label}을(를) 등록할 수 없습니다. 다른 앱이 사용 중이거나 시스템 예약 조합일 수 있습니다. 다른 조합을 선택하세요.",
        "{label} n'a pas pu être enregistré : utilisé par une autre application ou réservé au système. Essayez autre chose.",
        "{label} konnte nicht registriert werden: evtl. von einer anderen App belegt oder systemreserviert. Bitte andere Kombination.",
        "No se pudo registrar {label}: puede estar en uso o reservado por el sistema. Pruebe otra combinación.",
    ),
    "热键 {label} 注册失败，请用托盘右键菜单截图，或在「设置热键…」里换一个组合。": (
        "热键 {label} 注册失败，请用托盘右键菜单截图，或在「设置热键…」里换一个组合。",
        "熱鍵 {label} 註冊失敗，請用系統匣右鍵選單截圖，或在「設定熱鍵…」裡換一個組合。",
        "Hotkey {label} failed to register. Use the tray menu to capture, or pick another combination in Set Hotkey.",
        "ショートカット {label} を登録できませんでした。トレイメニューからキャプチャするか、設定で別の組み合わせを選んでください。",
        "단축키 {label} 등록에 실패했습니다. 트레이 메뉴에서 캡처하거나 단축키 설정에서 다른 조합을 선택하세요.",
        "Échec d'enregistrement du raccourci {label}. Utilisez le menu de la barre ou choisissez une autre combinaison.",
        "Tastenkürzel {label} konnte nicht registriert werden. Nutzen Sie das Tray-Menü oder wählen Sie eine andere Kombination.",
        "No se pudo registrar {label}. Use el menú de la bandeja o elija otra combinación en Atajo de teclado.",
    ),
    "系统托盘不可用，无法常驻运行。": (
        "系统托盘不可用，无法常驻运行。", "系統匣不可用，無法常駐執行。",
        "System tray is unavailable; the app cannot stay resident.",
        "通知領域（トレイ）が利用できません。常駐できません。",
        "시스템 트레이를 사용할 수 없어 상주 실행할 수 없습니다.",
        "La barre des tâches est indisponible ; l'application ne peut pas rester en arrière-plan.",
        "Der Infobereich ist nicht verfügbar; die App kann nicht im Hintergrund bleiben.",
        "La bandeja del sistema no está disponible; la app no puede permanecer residente.",
    ),
    "全局热键 {label} 注册失败（可能被其他程序占用）。请在主窗口或托盘菜单「设置热键…」换一个组合，也可直接点主窗口的截图按钮。": (
        "全局热键 {label} 注册失败（可能被其他程序占用）。请在主窗口或托盘菜单「设置热键…」换一个组合，也可直接点主窗口的截图按钮。",
        "全域熱鍵 {label} 註冊失敗（可能被其他程式占用）。請在主視窗或系統匣選單「設定熱鍵…」換一個組合，或直接點主視窗的截圖按鈕。",
        "Global hotkey {label} failed to register (possibly taken by another app). Change it in the main window or tray menu, or use the Capture button in the main window.",
        "グローバル ショートカット {label} を登録できませんでした（他のアプリが使用中かもしれません）。メインウィンドウ/トレイの設定で変更するか、キャプチャ ボタンを使ってください。",
        "전역 단축키 {label} 등록 실패(다른 앱이 사용 중일 수 있습니다). 주 창/트레이 설정에서 변경하거나 주 창의 캡처 버튼을 사용하세요.",
        "Le raccourci global {label} n'a pas pu être enregistré (peut-être utilisé). Modifiez-le depuis la fenêtre principale ou la barre, ou utilisez le bouton Capturer.",
        "Globales Tastenkürzel {label} nicht registrierbar (evtl. belegt). Ändern Sie es im Hauptfenster/Tray oder nutzen Sie die Schaltfläche Aufnehmen.",
        "No se pudo registrar el atajo global {label} (posiblemente ocupado). Cámbielo en la ventana principal o la bandeja, o use el botón Capturar.",
    ),

    # ------------------------------------------------------------ 单实例提示
    "已请它把主窗口显示出来，请看任务栏。\n": (
        "已请它把主窗口显示出来，请看任务栏。\n", "已請它把主視窗顯示出來，請看工作列。\n",
        "Asked the running instance to show its window; check the taskbar.\n",
        "起動中のインスタンスにウィンドウ表示を要求しました。タスクバーを確認してください。\n",
        "실행 중인 인스턴스에 창 표시를 요청했습니다. 작업 표시줄을 확인하세요.\n",
        "Demande d'affichage envoyée à l'instance en cours ; regardez la barre des tâches.\n",
        "Die laufende Instanz wurde zum Anzeigen aufgefordert; prüfen Sie die Taskleiste.\n",
        "Se pidió a la instancia activa mostrar su ventana; revise la barra de tareas.\n",
    ),
    "托盘图标可能被收进了通知区折叠栏（点 ^ 展开看看）。\n": (
        "托盘图标可能被收进了通知区折叠栏（点 ^ 展开看看）。\n",
        "系統匣圖示可能被收進通知區摺疊列（點 ^ 展開看看）。\n",
        "The tray icon may be hidden in the notification overflow (click ^ to expand).\n",
        "トレイアイコンが通知領域の折りたたみに隠れている可能性があります（^ をクリック）。\n",
        "트레이 아이콘이 알림 영역 접힘 메뉴에 숨겨졌을 수 있습니다(^ 클릭하여 확장).\n",
        "L'icône est peut-être dans la zone repliée des notifications (cliquez sur ^).\n",
        "Das Tray-Symbol ist evtl. im ausgeblendeten Infobereich (auf ^ klicken).\n",
        "El icono puede estar en el área de notificaciones oculta (haga clic en ^).\n",
    ),
    "{app}已在后台运行（PID {pid}，启动于 {started}）。\n\n": (
        "{app}已在后台运行（PID {pid}，启动于 {started}）。\n\n",
        "{app}已在背景執行（PID {pid}，啟動於 {started}）。\n\n",
        "{app} is already running in the background (PID {pid}, started {started}).\n\n",
        "{app} は既にバックグラウンドで実行中です（PID {pid}, 開始 {started}）。\n\n",
        "{app}이(가) 백그라운드에서 실행 중입니다(PID {pid}, 시작 {started}).\n\n",
        "{app} est déjà en arrière-plan (PID {pid}, démarré {started}).\n\n",
        "{app} läuft bereits im Hintergrund (PID {pid}, gestartet {started}).\n\n",
        "{app} ya se ejecuta en segundo plano (PID {pid}, iniciado {started}).\n\n",
    ),
    "如果确实看不到任何窗口，多半是残留的后台实例。\n\n是否结束它并重新启动？（若有未保存的编辑内容会丢失）": (
        "如果确实看不到任何窗口，多半是残留的后台实例。\n\n是否结束它并重新启动？（若有未保存的编辑内容会丢失）",
        "如果確實看不到任何視窗，多半是殘留的背景實例。\n\n是否結束它並重新啟動？（若有未儲存的編輯內容會遺失）",
        "If you cannot see any window, it is probably a stale background instance.\n\nEnd it and restart? (Unsaved edits will be lost.)",
        "ウィンドウが見つからない場合、残存したバックグラウンド インスタンスの可能性があります。\n\n終了して再起動しますか？（未保存の編集は失われます）",
        "창이 보이지 않는다면 남아 있는 백그라운드 인스턴스일 수 있습니다.\n\n종료하고 다시 시작할까요? (저장하지 않은 편집 내용은 사라집니다)",
        "Si aucune fenêtre n'est visible, il s'agit probablement d'une instance résiduelle.\n\nLa terminer et redémarrer ? (Les modifications non enregistrées seront perdues.)",
        "Falls kein Fenster sichtbar ist, ist vermutlich eine verwaiste Instanz aktiv.\n\nBeenden und neu starten? (Ungespeicherte Änderungen gehen verloren.)",
        "Si no ve ninguna ventana, probablemente sea una instancia residual.\n\n¿Terminarla y reiniciar? (Se perderán los cambios no guardados.)",
    ),
    "结束后台实例未成功，但仍会尝试继续启动。\n若再次提示已在运行，请在任务管理器里结束残留的 pythonw.exe。": (
        "结束后台实例未成功，但仍会尝试继续启动。\n若再次提示已在运行，请在任务管理器里结束残留的 pythonw.exe。",
        "結束背景實例未成功，但仍會嘗試繼續啟動。\n若再次提示已在執行，請在工作管理員裡結束殘留的 pythonw.exe。",
        "Could not end the background instance; startup will still be attempted.\nIf it happens again, end the leftover pythonw.exe in Task Manager.",
        "バックグラウンド インスタンスを終了できませんでしたが、起動を続けます。\n再度表示される場合はタスク マネージャーで残存 pythonw.exe を終了してください。",
        "백그라운드 인스턴스를 종료하지 못했지만 시작을 계속 시도합니다.\n다시 나타나면 작업 관리자에서 남은 pythonw.exe를 종료하세요.",
        "Impossible de terminer l'instance ; le démarrage continue malgré tout.\nSi le message revient, terminez pythonw.exe dans le Gestionnaire des tâches.",
        "Die Hintergrundinstanz konnte nicht beendet werden; der Start wird trotzdem versucht.\nFalls erneut, beenden Sie pythonw.exe im Task-Manager.",
        "No se pudo cerrar la instancia; se intentará iniciar de todos modos.\nSi vuelve a aparecer, cierre pythonw.exe en el Administrador de tareas.",
    ),
    "仍有实例占用，启动中止。请在任务管理器中结束所有 pythonw.exe 后重试，或双击 restart.bat。": (
        "仍有实例占用，启动中止。请在任务管理器中结束所有 pythonw.exe 后重试，或双击 restart.bat。",
        "仍有實例占用，啟動中止。請在工作管理員中結束所有 pythonw.exe 後重試，或雙擊 restart.bat。",
        "Another instance still holds the lock; startup aborted. End all pythonw.exe in Task Manager and retry, or double-click restart.bat.",
        "別のインスタンスがロックを保持しているため起動を中止しました。タスク マネージャーで pythonw.exe を終了して再試行するか、restart.bat をダブルクリックしてください。",
        "다른 인스턴스가 잠금을 유지하고 있어 시작을 중단했습니다. 작업 관리자에서 pythonw.exe를 모두 종료하고 다시 시도하거나 restart.bat을 실행하세요.",
        "Une autre instance occupe le verrou ; démarrage interrompu. Terminez tous les pythonw.exe puis réessayez, ou lancez restart.bat.",
        "Eine andere Instanz hält die Sperre; Start abgebrochen. Beenden Sie alle pythonw.exe und versuchen Sie es erneut, oder starten Sie restart.bat.",
        "Otra instancia mantiene el bloqueo; inicio abortado. Cierre todos los pythonw.exe y reintente, o ejecute restart.bat.",
    ),

    # ------------------------------------------------------------ 自检日志
    " 自检 ": (" 自检 ", " 自我檢測 ", " Self Test ", " セルフテスト ", " 자체 검사 ", " Auto-test ", " Selbsttest ", " Autoprueba "),
    " 可用": (" 可用", " 可用", " available", " 利用可能", " 사용 가능", " disponible", " verfügbar", " disponible"),
    " 未安装（对应功能不可用）": (
        " 未安装（对应功能不可用）", " 未安裝（對應功能不可用）", " not installed (feature unavailable)",
        " 未インストール（機能は利用不可）", " 설치되지 않음(기능 사용 불가)", " non installé (fonction indisponible)",
        " nicht installiert (Funktion nicht verfügbar)", " no instalado (función no disponible)",
    ),
    "测试图   : ": ("测试图   : ", "測試圖   : ", "Test image: ", "テスト画像: ", "테스트 이미지: ", "Image de test : ", "Testbild: ", "Imagen de prueba: "),
    "[FAIL] 找不到 ocr_test.png": (
        "[FAIL] 找不到 ocr_test.png", "[FAIL] 找不到 ocr_test.png", "[FAIL] ocr_test.png not found",
        "[FAIL] ocr_test.png が見つかりません", "[FAIL] ocr_test.png을 찾을 수 없습니다",
        "[FAIL] ocr_test.png introuvable", "[FAIL] ocr_test.png nicht gefunden", "[FAIL] no se encontró ocr_test.png",
    ),
    "[FAIL] OCR 返回 0 行": (
        "[FAIL] OCR 返回 0 行", "[FAIL] OCR 回傳 0 行", "[FAIL] OCR returned 0 lines",
        "[FAIL] OCR の結果が 0 行です", "[FAIL] OCR 결과가 0줄입니다", "[FAIL] OCR a renvoyé 0 ligne",
        "[FAIL] OCR lieferte 0 Zeilen", "[FAIL] OCR devolvió 0 líneas",
    ),
    "[selftest] 日志：{log}": (
        "[selftest] 日志：{log}", "[selftest] 日誌：{log}", "[selftest] Log: {log}",
        "[selftest] ログ: {log}", "[selftest] 로그: {log}", "[selftest] Journal : {log}",
        "[selftest] Protokoll: {log}", "[selftest] Registro: {log}",
    ),
}
_ROWS.update({
    # ------------------------------------------------------------ 热键对话框
    "小键盘 {n}": (
        "小键盘 {n}", "數字鍵盤 {n}", "Numpad {n}", "テンキー {n}", "숫자 키패드 {n}",
        "Pavé numérique {n}", "Ziffernblock {n}", "Teclado numérico {n}",
    ),
    "设置截图热键 - {app}": (
        "设置截图热键 - {app}", "設定截圖熱鍵 - {app}", "Set Capture Hotkey - {app}",
        "ショートカット設定 - {app}", "캡처 단축키 설정 - {app}", "Raccourci de capture - {app}",
        "Aufnahme-Tastenkürzel - {app}", "Atajo de captura - {app}",
    ),
    "当前热键：<b>{label}</b>": (
        "当前热键：<b>{label}</b>", "目前熱鍵：<b>{label}</b>", "Current hotkey: <b>{label}</b>",
        "現在のショートカット: <b>{label}</b>", "현재 단축키: <b>{label}</b>",
        "Raccourci actuel : <b>{label}</b>", "Aktuelles Tastenkürzel: <b>{label}</b>",
        "Atajo actual: <b>{label}</b>",
    ),
    "点这里后直接按下想要的组合键": (
        "点这里后直接按下想要的组合键", "點這裡後直接按下想要的組合鍵",
        "Click here, then press the desired key combination",
        "ここをクリックして目的のキーの組み合わせを押してください",
        "여기를 클릭한 뒤 원하는 키 조합을 누르세요",
        "Cliquez ici, puis appuyez sur la combinaison souhaitée",
        "Hier klicken, dann die gewünschte Tastenkombination drücken",
        "Haga clic aquí y pulse la combinación deseada",
    ),
    "点上方按钮后，按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键（如 Ctrl + Shift + S）。按 Esc 可放弃本次录制。": (
        "点上方按钮后，按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键（如 Ctrl + Shift + S）。按 Esc 可放弃本次录制。",
        "點上方按鈕後，按住 Ctrl / Alt / Shift / Win 中至少一個，再按一個主鍵（如 Ctrl + Shift + S）。按 Esc 可放棄本次錄製。",
        "Click the button above, hold at least one of Ctrl / Alt / Shift / Win, then press a main key (e.g. Ctrl + Shift + S). Press Esc to abort.",
        "上のボタンをクリックし、Ctrl / Alt / Shift / Win のいずれかを押しながら主キーを押します（例 Ctrl + Shift + S）。Esc で中止。",
        "위 버튼을 클릭한 뒤 Ctrl / Alt / Shift / Win 중 하나 이상을 누르고 기본 키를 누르세요(예: Ctrl + Shift + S). Esc로 취소합니다.",
        "Cliquez sur le bouton, maintenez au moins une touche Ctrl / Alt / Shift / Win puis une touche principale (ex. Ctrl + Shift + S). Échap pour annuler.",
        "Button oben klicken, mindestens eine Taste Ctrl / Alt / Shift / Win halten und eine Haupttaste drücken (z. B. Ctrl + Shift + S). Esc bricht ab.",
        "Pulse el botón, mantenga al menos Ctrl / Alt / Shift / Win y pulse una tecla principal (p. ej. Ctrl + Shift + S). Esc cancela.",
    ),
    "主键": ("主键", "主鍵", "Main Key", "主キー", "기본 키", "Touche principale", "Haupttaste", "Tecla principal"),
    "录制不到某些键（如 Win 组合）时，也可以在这里手动选择。": (
        "录制不到某些键（如 Win 组合）时，也可以在这里手动选择。",
        "錄製不到某些鍵（如 Win 組合）時，也可以在這裡手動選擇。",
        "If a combination (such as a Win shortcut) cannot be recorded, choose it manually here.",
        "一部の組み合わせ（Win など）を録音できない場合は、ここで手動選択してください。",
        "Win 조합처럼 기록할 수 없는 키는 여기에서 직접 선택하세요.",
        "Si une combinaison (comme Win) ne peut pas être enregistrée, sélectionnez-la ici manuellement.",
        "Falls eine Kombination (z. B. mit Win) nicht aufnehmbar ist, hier manuell wählen.",
        "Si alguna combinación (como Win) no se puede grabar, selecciónela aquí manualmente.",
    ),
    "恢复默认": ("恢复默认", "還原預設", "Restore Default", "既定に戻す", "기본값 복원", "Valeur par défaut", "Standard wiederherstellen", "Restaurar predeterminado"),
    "未选择修饰键": (
        "未选择修饰键", "未選擇修飾鍵", "No modifier selected", "修飾キー未選択",
        "보조 키 미선택", "Aucun modificateur", "Keine Modifikatortaste", "Sin tecla modificadora",
    ),
    "已恢复为 {label}，点「保存」生效。": (
        "已恢复为 {label}，点「保存」生效。", "已還原為 {label}，點「儲存」生效。",
        "Restored to {label}. Click Save to apply.", "{label} に戻しました。「保存」をクリックして適用します。",
        "{label}(으)로 복원했습니다. 저장을 누르면 적용됩니다.",
        "Rétabli à {label}. Cliquez sur Enregistrer pour appliquer.",
        "Auf {label} zurückgesetzt. Mit Speichern übernehmen.",
        "Restaurado a {label}. Pulse Guardar para aplicar.",
    ),
    "请按下组合键…": (
        "请按下组合键…", "請按下組合鍵…", "Press a key combination…", "キーの組み合わせを押してください…",
        "키 조합을 누르세요…", "Appuyez sur une combinaison…", "Tastenkombination drücken…", "Pulse una combinación…",
    ),
    "正在录制：按住修饰键再按主键（Esc 放弃录制）": (
        "正在录制：按住修饰键再按主键（Esc 放弃录制）", "正在錄製：按住修飾鍵再按主鍵（Esc 放棄錄製）",
        "Recording: hold a modifier, then press a main key (Esc to abort)",
        "録音中：修飾キーを押しながら主キーを押してください（Esc で中止）",
        "기록 중: 보조 키를 누른 채 기본 키를 누르세요(Esc로 취소)",
        "Enregistrement : maintenez un modificateur puis une touche principale (Échap pour annuler)",
        "Aufnahme: Modifikatortaste halten, dann Haupttaste drücken (Esc bricht ab)",
        "Grabando: mantenga un modificador y pulse una tecla principal (Esc cancela)",
    ),
    "已放弃录制，可点上方按钮重试，或直接手动选择。": (
        "已放弃录制，可点上方按钮重试，或直接手动选择。", "已放棄錄製，可點上方按鈕重試，或直接手動選擇。",
        "Recording cancelled. Click the button above to retry, or choose manually.",
        "録音を中止しました。上のボタンで再試行するか、手動で選択してください。",
        "기록을 취소했습니다. 위 버튼으로 다시 시도하거나 직접 선택하세요.",
        "Enregistrement annulé. Réessayez avec le bouton ou choisissez manuellement.",
        "Aufnahme abgebrochen. Oben erneut versuchen oder manuell wählen.",
        "Grabación cancelada. Reintente con el botón o elija manualmente.",
    ),
    "请按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键。": (
        "请按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键。",
        "請按住 Ctrl / Alt / Shift / Win 中至少一個，再按一個主鍵。",
        "Hold at least one of Ctrl / Alt / Shift / Win, then press a main key.",
        "Ctrl / Alt / Shift / Win のいずれかを押しながら主キーを押してください。",
        "Ctrl / Alt / Shift / Win 중 하나 이상을 누른 채 기본 키를 누르세요.",
        "Maintenez au moins une touche Ctrl / Alt / Shift / Win, puis une touche principale.",
        "Mindestens eine Taste Ctrl / Alt / Shift / Win halten und eine Haupttaste drücken.",
        "Mantenga al menos Ctrl / Alt / Shift / Win y pulse una tecla principal.",
    ),
    "已录制：{label}。点「保存」生效。": (
        "已录制：{label}。点「保存」生效。", "已錄製：{label}。點「儲存」生效。",
        "Recorded: {label}. Click Save to apply.", "録音しました: {label}。「保存」で適用します。",
        "기록됨: {label}. 저장을 누르면 적용됩니다.", "Enregistré : {label}. Cliquez sur Enregistrer pour appliquer.",
        "Aufgenommen: {label}. Mit Speichern übernehmen.", "Grabado: {label}. Pulse Guardar para aplicar.",
    ),
    "请至少选择一个修饰键（Ctrl / Alt / Shift / Win），并指定主键。": (
        "请至少选择一个修饰键（Ctrl / Alt / Shift / Win），并指定主键。",
        "請至少選擇一個修飾鍵（Ctrl / Alt / Shift / Win），並指定主鍵。",
        "Select at least one modifier (Ctrl / Alt / Shift / Win) and a main key.",
        "修飾キー（Ctrl / Alt / Shift / Win）を 1 つ以上選び、主キーを指定してください。",
        "보조 키(Ctrl / Alt / Shift / Win)를 하나 이상 선택하고 기본 키를 지정하세요.",
        "Sélectionnez au moins un modificateur (Ctrl / Alt / Shift / Win) et une touche principale.",
        "Mindestens einen Modifikator (Ctrl / Alt / Shift / Win) und eine Haupttaste wählen.",
        "Seleccione al menos un modificador (Ctrl / Alt / Shift / Win) y una tecla principal.",
    ),

    # ------------------------------------------------------------ 标注工具 / 工具条
    "矩形": ("矩形", "矩形", "Rectangle", "四角形", "사각형", "Rectangle", "Rechteck", "Rectángulo"),
    "椭圆": ("椭圆", "橢圓", "Ellipse", "楕円", "타원", "Ellipse", "Ellipse", "Elipse"),
    "箭头": ("箭头", "箭頭", "Arrow", "矢印", "화살표", "Flèche", "Pfeil", "Flecha"),
    "直线": ("直线", "直線", "Line", "直線", "직선", "Ligne", "Linie", "Línea"),
    "画笔": ("画笔", "畫筆", "Pen", "ペン", "펜", "Crayon", "Stift", "Lápiz"),
    "马赛克": ("马赛克", "馬賽克", "Mosaic", "モザイク", "모자이크", "Mosaïque", "Mosaik", "Mosaico"),
    "文字": ("文字", "文字", "Text", "テキスト", "텍스트", "Texte", "Text", "Texto"),
    "撤销上一步标注 (Ctrl+Z)": (
        "撤销上一步标注 (Ctrl+Z)", "復原上一步標註 (Ctrl+Z)", "Undo last annotation (Ctrl+Z)",
        "直前の注釈を取り消す (Ctrl+Z)", "마지막 주석 실행 취소 (Ctrl+Z)",
        "Annuler la dernière annotation (Ctrl+Z)", "Letzte Markierung rückgängig (Ctrl+Z)",
        "Deshacer última anotación (Ctrl+Z)",
    ),
    "顺时针旋转 90° (Ctrl+R)": (
        "顺时针旋转 90° (Ctrl+R)", "順時針旋轉 90° (Ctrl+R)", "Rotate 90° clockwise (Ctrl+R)",
        "時計回りに 90° 回転 (Ctrl+R)", "시계 방향 90° 회전 (Ctrl+R)",
        "Rotation 90° horaire (Ctrl+R)", "90° im Uhrzeigersinn (Ctrl+R)", "Rotar 90° horario (Ctrl+R)",
    ),
    "逆时针旋转 90° (Ctrl+Shift+R)": (
        "逆时针旋转 90° (Ctrl+Shift+R)", "逆時針旋轉 90° (Ctrl+Shift+R)",
        "Rotate 90° counter-clockwise (Ctrl+Shift+R)", "反時計回りに 90° 回転 (Ctrl+Shift+R)",
        "반시계 방향 90° 회전 (Ctrl+Shift+R)", "Rotation 90° antihoraire (Ctrl+Shift+R)",
        "90° gegen den Uhrzeigersinn (Ctrl+Shift+R)", "Rotar 90° antihorario (Ctrl+Shift+R)",
    ),
    "左右镜像 / 水平翻转 (Ctrl+H)": (
        "左右镜像 / 水平翻转 (Ctrl+H)", "左右鏡像 / 水平翻轉 (Ctrl+H)",
        "Mirror horizontally (Ctrl+H)", "左右反転 (Ctrl+H)", "좌우 반전 (Ctrl+H)",
        "Miroir horizontal (Ctrl+H)", "Horizontal spiegeln (Ctrl+H)", "Espejo horizontal (Ctrl+H)",
    ),
    "上下镜像 / 垂直翻转 (Ctrl+Shift+H)": (
        "上下镜像 / 垂直翻转 (Ctrl+Shift+H)", "上下鏡像 / 垂直翻轉 (Ctrl+Shift+H)",
        "Mirror vertically (Ctrl+Shift+H)", "上下反転 (Ctrl+Shift+H)", "상하 반전 (Ctrl+Shift+H)",
        "Miroir vertical (Ctrl+Shift+H)", "Vertikal spiegeln (Ctrl+Shift+H)", "Espejo vertical (Ctrl+Shift+H)",
    ),
    "滚动长截图": ("滚动长截图", "捲動長截圖", "Scrolling Capture", "スクロールキャプチャ", "스크롤 캡처", "Capture défilante", "Scroll-Aufnahme", "Captura larga"),
    "识别选区文字 (OCR)": (
        "识别选区文字 (OCR)", "辨識選區文字 (OCR)", "Recognize Text (OCR)", "テキスト認識 (OCR)",
        "문자 인식 (OCR)", "Reconnaître le texte (OCR)", "Text erkennen (OCR)", "Reconocer texto (OCR)",
    ),
    "另存为文件 (Ctrl+S)": (
        "另存为文件 (Ctrl+S)", "另存為檔案 (Ctrl+S)", "Save as File (Ctrl+S)", "名前を付けて保存 (Ctrl+S)",
        "파일로 저장 (Ctrl+S)", "Enregistrer sous (Ctrl+S)", "Speichern unter (Ctrl+S)", "Guardar como (Ctrl+S)",
    ),
    "复制到剪贴板 (Enter)": (
        "复制到剪贴板 (Enter)", "複製到剪貼簿 (Enter)", "Copy to Clipboard (Enter)",
        "クリップボードにコピー (Enter)", "클립보드에 복사 (Enter)", "Copier dans le presse-papiers (Enter)",
        "In die Zwischenablage (Enter)", "Copiar al portapapeles (Enter)",
    ),
    "确认选区，进入程序窗口继续编辑 (Enter)": (
        "确认选区，进入程序窗口继续编辑 (Enter)", "確認選區，進入程式視窗繼續編輯 (Enter)",
        "Confirm selection and continue editing in the app window (Enter)",
        "範囲を確定して編集ウィンドウへ (Enter)", "영역 확정 후 편집 창으로 (Enter)",
        "Valider la sélection et continuer dans la fenêtre (Enter)",
        "Auswahl bestätigen und im Fenster bearbeiten (Enter)", "Confirmar selección y editar en la ventana (Enter)",
    ),
    "取消 (Esc)": ("取消 (Esc)", "取消 (Esc)", "Cancel (Esc)", "キャンセル (Esc)", "취소 (Esc)", "Annuler (Esc)", "Abbrechen (Esc)", "Cancelar (Esc)"),

    # ------------------------------------------------------------ 样式面板
    "颜色": ("颜色", "顏色", "Color", "色", "색상", "Couleur", "Farbe", "Color"),
    "自定义颜色…": ("自定义颜色…", "自訂顏色…", "Custom Color…", "カスタム色…", "사용자 지정 색…", "Couleur personnalisée…", "Eigene Farbe…", "Color personalizado…"),
    "线宽": ("线宽", "線寬", "Line Width", "線の太さ", "선 두께", "Épaisseur du trait", "Linienbreite", "Grosor de línea"),
    "线型": ("线型", "線型", "Line Style", "線種", "선 스타일", "Style de trait", "Linienstil", "Estilo de línea"),
    "实线": ("实线", "實線", "Solid", "実線", "실선", "Plein", "Durchgezogen", "Sólida"),
    "虚线": ("虚线", "虛線", "Dashed", "破線", "파선", "Tirets", "Gestrichelt", "Discontinua"),
    "点线": ("点线", "點線", "Dotted", "点線", "점선", "Pointillés", "Gepunktet", "Punteada"),
    "填充色": ("填充色", "填滿色", "Fill Color", "塗りつぶし色", "채우기 색", "Couleur de remplissage", "Füllfarbe", "Color de relleno"),
    "启用": ("启用", "啟用", "Enable", "有効", "사용", "Activer", "Aktivieren", "Activar"),
    "字号": ("字号", "字級", "Font Size", "文字サイズ", "글자 크기", "Taille de police", "Schriftgröße", "Tamaño de fuente"),
    "加粗": ("加粗", "粗體", "Bold", "太字", "굵게", "Gras", "Fett", "Negrita"),
    "文字背景色": ("文字背景色", "文字背景色", "Text Background", "文字の背景色", "텍스트 배경색", "Fond du texte", "Texthintergrund", "Fondo del texto"),
    "端点箭头": ("端点箭头", "端點箭頭", "Endpoint Arrows", "端点の矢印", "끝점 화살표", "Flèches aux extrémités", "Pfeile an Endpunkten", "Flechas en los extremos"),
    "起点加箭头": ("起点加箭头", "起點加箭頭", "Arrow at Start", "始点に矢印", "시작점에 화살표", "Flèche au début", "Pfeil am Anfang", "Flecha al inicio"),
    "终点加箭头": ("终点加箭头", "終點加箭頭", "Arrow at End", "終点に矢印", "끝점에 화살표", "Flèche à la fin", "Pfeil am Ende", "Flecha al final"),
    "文字颜色": ("文字颜色", "文字顏色", "Text Color", "文字色", "텍스트 색", "Couleur du texte", "Textfarbe", "Color del texto"),
    "线条颜色": ("线条颜色", "線條顏色", "Line Color", "線の色", "선 색상", "Couleur du trait", "Linienfarbe", "Color de línea"),
    "选择颜色": ("选择颜色", "選擇顏色", "Select Color", "色を選択", "색 선택", "Choisir une couleur", "Farbe wählen", "Elegir color"),

    # ------------------------------------------------------------ OCR 取字
    "正在识别文字…": (
        "正在识别文字…", "正在辨識文字…", "Recognizing text…", "文字を認識しています…",
        "문자를 인식하는 중…", "Reconnaissance du texte…", "Text wird erkannt…", "Reconociendo texto…",
    ),
    "复制选中": ("复制选中", "複製選取", "Copy Selection", "選択範囲をコピー", "선택 영역 복사", "Copier la sélection", "Auswahl kopieren", "Copiar selección"),
    "复制全部": ("复制全部", "複製全部", "Copy All", "すべてコピー", "전체 복사", "Tout copier", "Alles kopieren", "Copiar todo"),
    "取字": ("取字", "取字", "Text Extraction", "文字抽出", "문자 추출", "Extraction de texte", "Texterkennung", "Extracción de texto"),
    "已复制到剪贴板 ✓": (
        "已复制到剪贴板 ✓", "已複製到剪貼簿 ✓", "Copied to clipboard ✓",
        "クリップボードにコピーしました ✓", "클립보드에 복사됨 ✓",
        "Copié dans le presse-papiers ✓", "In die Zwischenablage kopiert ✓", "Copiado al portapapeles ✓",
    ),
    "识别结果{tag} · 可拖选文字，Ctrl+C 或点下方按钮复制": (
        "识别结果{tag} · 可拖选文字，Ctrl+C 或点下方按钮复制",
        "辨識結果{tag} · 可拖選文字，Ctrl+C 或點下方按鈕複製",
        "Recognition result{tag} · Select text, Ctrl+C or use the buttons below",
        "認識結果{tag} · テキストを選択し Ctrl+C または下のボタンでコピー",
        "인식 결과{tag} · 텍스트를 선택하고 Ctrl+C 또는 아래 버튼으로 복사",
        "Résultat{tag} · Sélectionnez le texte, Ctrl+C ou les boutons ci-dessous",
        "Ergebnis{tag} · Text markieren, Ctrl+C oder Schaltflächen unten",
        "Resultado{tag} · Seleccione texto, Ctrl+C o los botones de abajo",
    ),
    "识别结果": ("识别结果", "辨識結果", "Recognition Result", "認識結果", "인식 결과", "Résultat", "Ergebnis", "Resultado"),
    "识别到 {n} 行{tag} · 拖选文字后 Ctrl+C 复制，复制完自动返回": (
        "识别到 {n} 行{tag} · 拖选文字后 Ctrl+C 复制，复制完自动返回",
        "辨識到 {n} 行{tag} · 拖選文字後 Ctrl+C 複製，複製完自動返回",
        "{n} lines recognized{tag} · Select text and press Ctrl+C; returns automatically after copying",
        "{n} 行を認識{tag} · テキストを選択して Ctrl+C、コピー後は自動で戻ります",
        "{n}줄 인식됨{tag} · 텍스트 선택 후 Ctrl+C, 복사하면 자동으로 돌아갑니다",
        "{n} lignes reconnues{tag} · Sélectionnez et Ctrl+C ; retour automatique après copie",
        "{n} Zeilen erkannt{tag} · Text markieren und Ctrl+C; danach automatische Rückkehr",
        "{n} líneas reconocidas{tag} · Seleccione y pulse Ctrl+C; vuelve automáticamente",
    ),
    "请先用鼠标拖选某一行文字，或点「复制全部」": (
        "请先用鼠标拖选某一行文字，或点「复制全部」", "請先用滑鼠拖選某一行文字，或點「複製全部」",
        "Select a line of text first, or click Copy All", "まずテキスト行を選択するか、「すべてコピー」をクリック",
        "먼저 텍스트 줄을 선택하거나 '전체 복사'를 누르세요", "Sélectionnez d'abord une ligne ou cliquez sur Tout copier",
        "Zuerst eine Textzeile markieren oder Alles kopieren klicken", "Seleccione una línea o pulse Copiar todo",
    ),
    "窗口截图：移动鼠标到目标窗口，单击确认    右键 / Esc 取消": (
        "窗口截图：移动鼠标到目标窗口，单击确认    右键 / Esc 取消",
        "視窗截圖：移動滑鼠到目標視窗，單擊確認    右鍵 / Esc 取消",
        "Window Capture: hover over a window and click to confirm    Right-click / Esc to cancel",
        "ウィンドウキャプチャ: カーソルを合わせてクリックで確定    右クリック / Esc で取消",
        "창 캡처: 창 위로 마우스를 옮기고 클릭하여 확정    오른쪽 클릭 / Esc로 취소",
        "Capture de fenêtre : survolez une fenêtre et cliquez    Clic droit / Échap pour annuler",
        "Fensteraufnahme: Fenster unter dem Zeiger anklicken    Rechtsklick / Esc bricht ab",
        "Captura de ventana: sitúese sobre la ventana y haga clic    Clic derecho / Esc cancela",
    ),
    "按住鼠标左键框选区域    Esc 取消": (
        "按住鼠标左键框选区域    Esc 取消", "按住滑鼠左鍵框選區域    Esc 取消",
        "Drag with the left mouse button to select an area    Esc to cancel",
        "左ボタンをドラッグして範囲を選択    Esc で取消",
        "마우스 왼쪽 버튼으로 드래그하여 영역 선택    Esc로 취소",
        "Glisser avec le bouton gauche pour sélectionner    Échap pour annuler",
        "Mit linker Maustaste einen Bereich ziehen    Esc bricht ab",
        "Arrastre con el botón izquierdo para seleccionar    Esc cancela",
    ),

    # ------------------------------------------------------------ 编辑器菜单
    "复制到剪贴板\tCtrl+Enter": (
        "复制到剪贴板\tCtrl+Enter", "複製到剪貼簿\tCtrl+Enter", "Copy to Clipboard\tCtrl+Enter",
        "クリップボードにコピー\tCtrl+Enter", "클립보드에 복사\tCtrl+Enter",
        "Copier dans le presse-papiers\tCtrl+Enter", "In die Zwischenablage\tCtrl+Enter", "Copiar al portapapeles\tCtrl+Enter",
    ),
    "另存为…\tCtrl+S": ("另存为…\tCtrl+S", "另存為…\tCtrl+S", "Save As…\tCtrl+S", "名前を付けて保存…\tCtrl+S", "다른 이름으로 저장…\tCtrl+S", "Enregistrer sous…\tCtrl+S", "Speichern unter…\tCtrl+S", "Guardar como…\tCtrl+S"),
    "关闭编辑器\tEsc": ("关闭编辑器\tEsc", "關閉編輯器\tEsc", "Close Editor\tEsc", "エディターを閉じる\tEsc", "편집기 닫기\tEsc", "Fermer l'éditeur\tEsc", "Editor schließen\tEsc", "Cerrar editor\tEsc"),
    "编辑(&E)": ("编辑(&E)", "編輯(&E)", "Edit(&E)", "編集(&E)", "편집(&E)", "Édition(&E)", "Bearbeiten(&E)", "Editar(&E)"),
    "撤销\tCtrl+Z": ("撤销\tCtrl+Z", "復原\tCtrl+Z", "Undo\tCtrl+Z", "元に戻す\tCtrl+Z", "실행 취소\tCtrl+Z", "Annuler\tCtrl+Z", "Rückgängig\tCtrl+Z", "Deshacer\tCtrl+Z"),
    "OCR 取字": ("OCR 取字", "OCR 取字", "OCR Text", "OCR 文字抽出", "OCR 문자 추출", "OCR Texte", "OCR Text", "OCR Texto"),
    "样式面板": ("样式面板", "樣式面板", "Style Panel", "スタイル パネル", "스타일 패널", "Panneau de style", "Stilpanel", "Panel de estilo"),
    "图像变换": ("图像变换", "影像變換", "Transform", "画像変換", "이미지 변환", "Transformation", "Bildtransformation", "Transformar"),
    "顺时针旋转 90°": ("顺时针旋转 90°", "順時針旋轉 90°", "Rotate 90° Clockwise", "時計回りに 90° 回転", "시계 방향 90° 회전", "Rotation 90° horaire", "90° im Uhrzeigersinn", "Rotar 90° horario"),
    "逆时针旋转 90°": ("逆时针旋转 90°", "逆時針旋轉 90°", "Rotate 90° Counter-clockwise", "反時計回りに 90° 回転", "반시계 방향 90° 회전", "Rotation 90° antihoraire", "90° gegen den Uhrzeigersinn", "Rotar 90° antihorario"),
    "左右镜像": ("左右镜像", "左右鏡像", "Flip Horizontally", "左右反転", "좌우 반전", "Miroir horizontal", "Horizontal spiegeln", "Espejo horizontal"),
    "上下镜像": ("上下镜像", "上下鏡像", "Flip Vertically", "上下反転", "상하 반전", "Miroir vertical", "Vertikal spiegeln", "Espejo vertical"),
    "不加箭头": ("不加箭头", "不加箭頭", "No Arrows", "矢印なし", "화살표 없음", "Aucune flèche", "Keine Pfeile", "Sin flechas"),
    "只加起点": ("只加起点", "只加起點", "Start Only", "始点のみ", "시작점만", "Début uniquement", "Nur Anfang", "Solo inicio"),
    "只加终点": ("只加终点", "只加終點", "End Only", "終点のみ", "끝점만", "Fin uniquement", "Nur Ende", "Solo final"),
    "两端都加": ("两端都加", "兩端都加", "Both Ends", "両端", "양쪽 모두", "Les deux extrémités", "Beide Enden", "Ambos extremos"),

    # ------------------------------------------------------------ 后端异常文案
    "拼接帧宽度必须一致": (
        "拼接帧宽度必须一致", "拼接幀寬度必須一致", "Stitched frames must have the same width",
        "結合するフレームの幅は同じでなければなりません", "결합할 프레임의 너비가 같아야 합니다",
        "Les images assemblées doivent avoir la même largeur", "Zusammenzufügende Bilder müssen gleiche Breite haben",
        "Los fotogramas deben tener el mismo ancho",
    ),
    "缺少依赖 {error}": (
        "缺少依赖 {error}", "缺少依賴 {error}", "Missing dependency {error}",
        "依存関係がありません {error}", "종속성 누락 {error}", "Dépendance manquante {error}",
        "Fehlende Abhängigkeit {error}", "Falta la dependencia {error}",
    ),
    "没有可用的 OCR 后端": (
        "没有可用的 OCR 后端", "沒有可用的 OCR 後端", "No OCR backend available",
        "利用可能な OCR バックエンドがありません", "사용 가능한 OCR 백엔드가 없습니다",
        "Aucun moteur OCR disponible", "Kein OCR-Backend verfügbar", "No hay motor OCR disponible",
    ),
    "未安装 winrt 包（Windows OCR 绑定）": (
        "未安装 winrt 包（Windows OCR 绑定）", "未安裝 winrt 套件（Windows OCR 綁定）",
        "winrt package is not installed (Windows OCR binding)",
        "winrt パッケージが未インストールです（Windows OCR バインディング）",
        "winrt 패키지가 설치되지 않았습니다(Windows OCR 바인딩)",
        "Le paquet winrt n'est pas installé (liaison Windows OCR)",
        "winrt-Paket nicht installiert (Windows-OCR-Bindung)",
        "El paquete winrt no está instalado (enlace Windows OCR)",
    ),
    "系统未安装可用的 OCR 语言包（需 zh-CN OCR 语言包）": (
        "系统未安装可用的 OCR 语言包（需 zh-CN OCR 语言包）",
        "系統未安裝可用的 OCR 語言包（需 zh-CN OCR 語言包）",
        "No usable OCR language pack is installed (zh-CN OCR pack required)",
        "使用可能な OCR 言語パックがありません（zh-CN OCR 言語パックが必要）",
        "사용 가능한 OCR 언어 팩이 없습니다(zh-CN OCR 팩 필요)",
        "Aucun module linguistique OCR utilisable (pack OCR zh-CN requis)",
        "Kein nutzbares OCR-Sprachpaket installiert (zh-CN OCR-Paket nötig)",
        "No hay paquete de idioma OCR utilizable (se requiere zh-CN OCR)",
    ),
    # ------------------------------------------------------------ 独立「滚动长截图」命令
    "滚动长截图…": (
        "滚动长截图…", "捲動長截圖…", "Scrolling Capture…", "スクロールキャプチャ…",
        "스크롤 캡처…", "Capture défilante…", "Scroll-Aufnahme…", "Captura larga…",
    ),
    "框选要滚动的区域，点「确定」开始自动拼接    Esc 取消": (
        "框选要滚动的区域，点「确定」开始自动拼接    Esc 取消",
        "框選要捲動的區域，點「確定」開始自動拼接    Esc 取消",
        "Drag to select the scrolling area, then click OK to stitch    Esc cancels",
        "スクロールする範囲をドラッグで選び、「OK」で結合開始    Esc で取消",
        "스크롤할 영역을 드래그한 뒤 확인을 누르면 자동 결합    Esc 취소",
        "Faites glisser pour choisir la zone, puis OK pour assembler    Esc annule",
        "Zum Aufnehmen Bereich ziehen, dann OK zum Zusammenfügen    Esc bricht ab",
        "Arrastre para elegir el área y pulse Aceptar para unir    Esc cancela",
    ),
    "开始滚动拼接 (Enter)": (
        "开始滚动拼接 (Enter)", "開始捲動拼接 (Enter)", "Start stitching (Enter)",
        "結合を開始 (Enter)", "결합 시작 (Enter)", "Démarrer l'assemblage (Entrée)",
        "Zusammenfügen starten (Enter)", "Iniciar unión (Enter)",
    ),
    # ------------------------------------------------------------ 选窗口式滚动长截图
    "点击窗口后自动滚动拼接成长图": (
        "点击窗口后自动滚动拼接成长图", "點擊視窗後自動捲動拼接成長圖",
        "Click a window to auto-scroll and stitch a long image",
        "ウィンドウをクリックすると自動スクロールで長い画像を結合",
        "창을 클릭하면 자동 스크롤로 긴 이미지를 만듭니다",
        "Cliquez sur une fenêtre pour l'assembler par défilement",
        "Fenster anklicken und automatisch zu einem langen Bild zusammenfügen",
        "Haga clic en una ventana para unirla al desplazarse",
    ),
    "单击选择要截长屏的窗口，自动向下滚屏    右键 / Esc 取消": (
        "单击选择要截长屏的窗口，自动向下滚屏    右键 / Esc 取消",
        "單擊選擇要截長圖的視窗，自動向下捲動    右鍵 / Esc 取消",
        "Click the window to capture — it scrolls down automatically    Right-click / Esc cancels",
        "キャプチャするウィンドウをクリックすると自動で下へスクロール    右クリック / Esc で取消",
        "캡처할 창을 클릭하면 자동으로 아래로 스크롤합니다    오른쪽 클릭 / Esc 취소",
        "Cliquez sur la fenêtre à capturer ; le défilement démarre seul    Clic droit / Échap annule",
        "Fenster anklicken; das Scrollen beginnt automatisch    Rechtsklick / Esc bricht ab",
        "Haga clic en la ventana; el desplazamiento empieza solo    Clic derecho / Esc cancela",
    ),
    "已暂停 · 左键继续": (
        "已暂停 · 左键继续", "已暫停 · 左鍵繼續", "Paused · left-click to resume",
        "一時停止中 · 左クリックで再開", "일시 정지 · 왼쪽 클릭으로 계속",
        "En pause · clic gauche pour reprendre", "Pausiert · Linksklick zum Fortsetzen",
        "En pausa · clic izquierdo para continuar",
    ),
    "已拼 {frames} 帧 · {height}px": (
        "已拼 {frames} 帧 · {height}px", "已拼 {frames} 幀 · {height}px",
        "{frames} frames · {height}px", "{frames} フレーム · {height}px",
        "{frames} 프레임 · {height}px", "{frames} images · {height}px",
        "{frames} Bilder · {height}px", "{frames} fotogramas · {height}px",
    ),
    "确定 ✓": (
        "确定 ✓", "確定 ✓", "Done ✓", "完了 ✓", "완료 ✓",
        "Terminé ✓", "Fertig ✓", "Listo ✓",
    ),
    "左键暂停 / 继续 · 右键或 Esc 结束 · 滚到底自动结束": (
        "左键暂停 / 继续 · 右键或 Esc 结束 · 滚到底自动结束",
        "左鍵暫停 / 繼續 · 右鍵或 Esc 結束 · 捲到底自動結束",
        "Left-click pauses / resumes · right-click or Esc ends · auto-ends at the bottom",
        "左クリックで一時停止 / 再開 · 右クリックまたは Esc で終了 · 最下部で自動終了",
        "왼쪽 클릭 일시정지 / 계속 · 오른쪽 클릭 또는 Esc 종료 · 맨 아래에서 자동 종료",
        "Clic gauche : pause / reprise · clic droit ou Échap : fin · fin automatique en bas",
        "Linksklick: Pause / Weiter · Rechtsklick oder Esc: Ende · automatisches Ende am Seitenende",
        "Clic izquierdo: pausa / continuar · clic derecho o Esc: fin · fin automática al final",
    ),
    "已滚动到底，长截图自动结束": (
        "已滚动到底，长截图自动结束", "已捲動到底，長截圖自動結束",
        "Reached the bottom — capture finished automatically",
        "最下部まで到達したため自動終了しました",
        "맨 아래까지 스크롤하여 자동으로 종료했습니다",
        "Bas de page atteint — capture terminée automatiquement",
        "Ende erreicht — Aufnahme automatisch beendet",
        "Se llegó al final — captura finalizada automáticamente",
    ),

    # -------------------------------------------------- v19 长截图结束诊断
    "匹配 {score}": (
        "匹配 {score}", "匹配 {score}", "Match {score}", "一致度 {score}",
        "일치도 {score}", "Correspondance {score}", "Übereinstimmung {score}",
        "Coincidencia {score}",
    ),
    "长截图完成 · 共 {frames} 帧 · {height}px": (
        "长截图完成 · 共 {frames} 帧 · {height}px",
        "長截圖完成 · 共 {frames} 幀 · {height}px",
        "Capture complete · {frames} frames · {height}px",
        "スクロール キャプチャ完了 · {frames} フレーム · {height}px",
        "스크롤 캡처 완료 · {frames} 프레임 · {height}px",
        "Capture terminée · {frames} images · {height}px",
        "Aufnahme abgeschlossen · {frames} Bilder · {height}px",
        "Captura completa · {frames} fotogramas · {height}px",
    ),
    "长截图提前结束：{reason} · 共 {frames} 帧 · 匹配 {score}": (
        "长截图提前结束：{reason} · 共 {frames} 帧 · 匹配 {score}",
        "長截圖提前結束：{reason} · 共 {frames} 幀 · 匹配 {score}",
        "Capture stopped early: {reason} · {frames} frames · match {score}",
        "途中で終了：{reason} · {frames} フレーム · 一致度 {score}",
        "조기 종료: {reason} · {frames} 프레임 · 일치도 {score}",
        "Capture interrompue : {reason} · {frames} images · corr. {score}",
        "Aufnahme vorzeitig beendet: {reason} · {frames} Bilder · Treffer {score}",
        "Captura interrumpida: {reason} · {frames} fotogramas · coinc. {score}",
    ),
    "内容无法自动对齐": (
        "内容无法自动对齐", "內容無法自動對齊", "Content could not be aligned",
        "位置合わせできませんでした", "자동 정렬 실패", "Alignement impossible",
        "Ausrichtung fehlgeschlagen", "No se pudo alinear",
    ),
    "页面没有新增内容": (
        "页面没有新增内容", "頁面沒有新增內容", "Page produced no new content",
        "ページに新しい内容がありません", "페이지에 새 내용이 없습니다",
        "Aucun nouveau contenu", "Kein neuer Inhalt", "Sin contenido nuevo",
    ),
    "帧数已达上限": (
        "帧数已达上限", "幀數已達上限", "Frame limit reached",
        "フレーム数が上限に達しました", "프레임 수 한도 도달",
        "Limite d'images atteinte", "Bildgrenze erreicht", "Límite de fotogramas",
    ),
    "高度已达上限": (
        "高度已达上限", "高度已達上限", "Height limit reached",
        "高さが上限に達しました", "높이 한도 도달",
        "Hauteur maximale atteinte", "Höhengrenze erreicht", "Altura máxima",
    ),

    # -------------------------------------------------- v19 透明色 / 填充透明度
    "透明（无边框）": (
        "透明（无边框）", "透明（無邊框）", "Transparent (no border)",
        "透明（枠なし）", "투명（테두리 없음）", "Transparent (sans bordure)",
        "Transparent (ohne Rand)", "Transparente (sin borde)",
    ),
    "填充透明度": (
        "填充透明度", "填色不透明度", "Fill opacity", "塗りつぶしの不透明度",
        "채우기 불투명도", "Opacité du remplissage", "Fülldeckkraft",
        "Opacidad de relleno",
    ),

    # -------------------------------------------------- v19 画布视图放缩
    "视图(&V)": (
        "视图(&V)", "檢視(&V)", "View(&V)", "表示(&V)", "보기(&V)",
        "Affichage(&V)", "Ansicht(&V)", "Ver(&V)",
    ),
    "放大": ("放大", "放大", "Zoom In", "拡大", "확대", "Zoom avant", "Vergrößern", "Acercar"),
    "缩小": ("缩小", "縮小", "Zoom Out", "縮小", "축소", "Zoom arrière", "Verkleinern", "Alejar"),
    "实际大小 1:1": (
        "实际大小 1:1", "實際大小 1:1", "Actual Size 1:1", "等倍 1:1",
        "실제 크기 1:1", "Taille réelle 1:1", "Originalgröße 1:1", "Tamaño real 1:1",
    ),
    "适应窗口": (
        "适应窗口", "配合視窗", "Fit to Window", "ウィンドウに合わせる",
        "창에 맞춤", "Ajuster à la fenêtre", "An Fenster anpassen", "Ajustar a la ventana",
    ),
    "缩放 {pct}%": (
        "缩放 {pct}%", "縮放 {pct}%", "Zoom {pct}%", "ズーム {pct}%",
        "확대 {pct}%", "Zoom {pct}%", "Zoom {pct}%", "Zoom {pct}%",
    ),

    # -------------------------------------------------- v22 形状旋转
    "旋转角度": (
        "旋转角度", "旋轉角度", "Rotation angle", "回転角度", "회전 각도",
        "Angle de rotation", "Drehwinkel", "Ángulo de rotación",
    ),
    "旋转选中形状": (
        "旋转选中形状", "旋轉選取形狀", "Rotate Selected Shape",
        "選択中の図形を回転", "선택한 도형 회전",
        "Pivoter la forme sélectionnée", "Ausgewählte Form drehen",
        "Rotar forma seleccionada",
    ),
    "顺时针旋转选中 90°": (
        "顺时针旋转选中 90°", "順時針旋轉選取 90°", "Rotate Selected 90° CW",
        "選択中を時計回りに 90°", "선택 항목 시계 방향 90°",
        "Rotation sélection 90° horaire", "Auswahl 90° im Uhrzeigersinn",
        "Rotar selección 90° horaria",
    ),
    "逆时针旋转选中 90°": (
        "逆时针旋转选中 90°", "逆時針旋轉選取 90°", "Rotate Selected 90° CCW",
        "選択中を反時計回りに 90°", "선택 항목 반시계 방향 90°",
        "Rotation sélection 90° antihoraire", "Auswahl 90° gegen den Uhrzeigersinn",
        "Rotar selección 90° antihoraria",
    ),

    # -------------------------------------------------- v23 文字背景边框
    "背景透明度": (
        "背景透明度", "背景透明度", "Background opacity", "背景の不透明度",
        "배경 불투명도", "Opacité du fond", "Hintergrund-Deckkraft",
        "Opacidad del fondo",
    ),
    "文字背景边框": (
        "文字背景边框", "文字背景框線", "Text background border", "文字背景の枠線",
        "텍스트 배경 테두리", "Bordure du fond du texte",
        "Rahmen des Texthintergrunds", "Borde del fondo del texto",
    ),
    "启用边框": (
        "启用边框", "啟用框線", "Enable border", "枠線を有効にする",
        "테두리 사용", "Activer la bordure", "Rahmen aktivieren",
        "Activar borde",
    ),
    "边框颜色": (
        "边框颜色", "框線顏色", "Border color", "枠線の色",
        "테두리 색상", "Couleur de la bordure", "Rahmenfarbe",
        "Color del borde",
    ),
    "边框线宽": (
        "边框线宽", "框線粗細", "Border width", "枠線の太さ",
        "테두리 두께", "Épaisseur de la bordure", "Rahmenstärke",
        "Grosor del borde",
    ),
    # ------------------------------------------------------------ v38 方案 E 界面
    "托盘常驻 · 关闭面板不会退出程序": (
        "托盘常驻 · 关闭面板不会退出程序", "常駐系統匣 · 關閉面板不會結束程式",
        "Runs in the tray · closing the panel won't quit",
        "常駐トレイ · パネルを閉じても終了しません",
        "트레이 상주 · 패널을 닫아도 종료되지 않음",
        "Réside dans la zone de notification · fermer ne quitte pas",
        "Bleibt im Infobereich · Schließen beendet nicht",
        "Permanece en la bandeja · cerrar no sale",
    ),
    "已启动": (
        "已启动", "已啟動", "Running", "起動中", "실행 중", "Actif", "Aktiv", "Activo",
    ),
    "编辑与输出": (
        "编辑与输出", "編輯與輸出", "Edit & Export", "編集と出力", "편집 및 출력",
        "Édition et export", "Bearbeiten & Ausgabe", "Edición y salida",
    ),
    "设置": (
        "设置", "設定", "Settings", "設定", "설정", "Réglages", "Einstellungen", "Ajustes",
    ),
    "帮助": (
        "帮助", "說明", "Help", "ヘルプ", "도움말", "Aide", "Hilfe", "Ayuda",
    ),
    "拖动选取任意区域 · 默认模式": (
        "拖动选取任意区域 · 默认模式", "拖曳選取任意區域 · 預設模式",
        "Drag to select any area · default mode",
        "ドラッグで範囲を選択 · 既定モード",
        "드래그하여 영역 선택 · 기본 모드",
        "Glisser pour sélectionner une zone · mode par défaut",
        "Ziehen zum Auswählen · Standardmodus",
        "Arrastra para seleccionar · modo predeterminado",
    ),
    "悬停高亮 · 单击确认": (
        "悬停高亮 · 单击确认", "懸停反白 · 按一下確認",
        "Hover to highlight · click to confirm",
        "ホバーで強調 · クリックで確定",
        "마우스를 올리면 강조 · 클릭하여 확인",
        "Survol pour surligner · clic pour valider",
        "Hover zum Hervorheben · Klick zum Bestätigen",
        "Resalta al pasar · clic para confirmar",
    ),
    "整块桌面 · 多屏合屏": (
        "整块桌面 · 多屏合屏", "整個桌面 · 多螢幕拼接",
        "Whole desktop · all monitors",
        "デスクトップ全体 · 全モニター",
        "전체 데스크톱 · 다중 모니터",
        "Bureau entier · tous les écrans",
        "Gesamter Desktop · alle Monitore",
        "Escritorio completo · todas las pantallas",
    ),
    "点击窗口自动滚屏成长图": (
        "点击窗口自动滚屏成长图", "點擊視窗自動捲動成長圖",
        "Click a window to auto-scroll into a long shot",
        "ウィンドウをクリックで自動スクロール",
        "창을 클릭하면 자동 스크롤",
        "Cliquez une fenêtre pour défiler",
        "Fenster anklicken, automatisch scrollen",
        "Clic en una ventana para desplazar",
    ),
    "识别选区文字 · 离线 RapidOCR": (
        "识别选区文字 · 离线 RapidOCR", "辨識選取區文字 · 離線 RapidOCR",
        "Read text in a region · offline RapidOCR",
        "範囲内の文字を認識 · オフライン RapidOCR",
        "선택 영역 텍스트 인식 · 오프라인 RapidOCR",
        "Lire le texte d'une zone · RapidOCR hors ligne",
        "Text im Bereich erkennen · offline RapidOCR",
        "Leer texto de una zona · RapidOCR sin conexión",
    ),
    "离线": (
        "离线", "離線", "Offline", "オフライン", "오프라인",
        "Hors ligne", "Offline", "Sin conexión",
    ),
    "钉成桌面浮窗 · 可拖动缩放": (
        "钉成桌面浮窗 · 可拖动缩放", "釘成桌面浮窗 · 可拖曳縮放",
        "Pin as a desktop overlay · drag & zoom",
        "デスクトップに固定 · 移動と拡大",
        "데스크톱에 고정 · 이동 및 확대",
        "Épingler sur le bureau · déplaçable",
        "Auf Desktop anheften · verschiebbar",
        "Fijar al escritorio · mover y zoom",
    ),
    "点击修改，立即生效": (
        "点击修改，立即生效", "點擊修改，立即生效",
        "Click to change · takes effect now",
        "クリックで変更 · すぐ反映",
        "클릭하여 변경 · 즉시 적용",
        "Cliquez pour modifier · effet immédiat",
        "Klicken zum Ändern · sofort wirksam",
        "Clic para cambiar · efecto inmediato",
    ),
    "独立于截图热键": (
        "独立于截图热键", "獨立於截圖熱鍵",
        "Separate from the capture hotkey",
        "キャプチャとは別のショートカット",
        "캡처 단축키와 별개",
        "Indépendant du raccourci de capture",
        "Unabhängig vom Aufnahme-Shortcut",
        "Independiente del atajo de captura",
    ),
    "8 种语言 · 可跟随系统": (
        "8 种语言 · 可跟随系统", "8 種語言 · 可跟隨系統",
        "8 languages · follows the system",
        "8 言語 · システムに追従",
        "8개 언어 · 시스템 설정 따름",
        "8 langues · suit le système",
        "8 Sprachen · folgt dem System",
        "8 idiomas · sigue al sistema",
    ),
    "关闭 / 轻度 / 中等 / 强": (
        "关闭 / 轻度 / 中等 / 强", "關閉 / 輕度 / 中等 / 強",
        "Off / Low / Medium / High",
        "オフ / 弱 / 中 / 強",
        "끔 / 약 / 중 / 강",
        "Désactivé / Léger / Moyen / Fort",
        "Aus / Leicht / Mittel / Stark",
        "Desactivado / Suave / Medio / Fuerte",
    ),
    "热键与托盘使用此模式": (
        "热键与托盘使用此模式", "熱鍵與系統匣使用此模式",
        "Used by the hotkey and tray",
        "ホットキーとトレイで使用",
        "단축키와 트레이에서 사용",
        "Utilisé par le raccourci et la zone de notification",
        "Von Hotkey und Infobereich genutzt",
        "Usado por el atajo y la bandeja",
    ),
    "10 个完整操作文档": (
        "10 个完整操作文档", "10 個完整操作文件",
        "10 topics, fully documented",
        "全 10 章の操作ガイド",
        "10개 전체 문서",
        "10 rubriques détaillées",
        "10 vollständige Kapitel",
        "10 temas completos",
    ),
    "版本信息 · 联系邮箱 · 退出程序": (
        "版本信息 · 联系邮箱 · 退出程序", "版本資訊 · 聯絡信箱 · 結束程式",
        "Version · contact · quit",
        "バージョン · 連絡先 · 終了",
        "버전 · 연락처 · 종료",
        "Version · contact · quitter",
        "Version · Kontakt · beenden",
        "Versión · contacto · salir",
    ),
    "关于与退出": (
        "关于与退出", "關於與結束", "About & Quit", "情報と終了", "정보 및 종료",
        "À propos et quitter", "Über & Beenden", "Acerca de y salir",
    ),
    "默认": (
        "默认", "預設", "Default", "既定", "기본",
        "Par défaut", "Standard", "Predeterminado",
    ),
    "默认方式": (
        "默认方式", "預設方式", "Default", "既定の方法", "기본 방식",
        "Méthode par défaut", "Standardmethode", "Método predeterminado",
    ),
    "拖动选取任意区域": (
        "拖动选取任意区域", "拖曳選取任意區域", "Drag to select any area",
        "ドラッグで範囲を選択", "드래그하여 영역 선택",
        "Glisser pour sélectionner une zone", "Bereich aufziehen",
        "Arrastra para seleccionar",
    ),
    "命令面板": (
        "命令面板", "命令面板", "Command Panel", "コマンドパネル", "명령 패널",
        "Panneau de commandes", "Befehlspanel", "Panel de comandos",
    ),
    "选择": (
        "选择", "選取", "Select", "選択", "선택",
        "Sélection", "Auswählen", "Seleccionar",
    ),
    "菜单": (
        "菜单", "選單", "Menu", "メニュー", "메뉴", "Menu", "Menü", "Menú",
    ),
    "贴图热键": (
        "贴图热键", "貼圖熱鍵", "Pin Hotkey", "ピン留めのショートカット",
        "고정 단축키", "Raccourci d'épinglage", "Anheft-Shortcut", "Atajo de fijado",
    ),
    "默认截图模式": (
        "默认截图模式", "預設截圖模式", "Default Capture Mode", "既定のキャプチャモード",
        "기본 캡처 모드", "Mode de capture par défaut", "Standard-Aufnahmemodus",
        "Modo de captura predeterminado",
    ),
    "框选模式 · 拖动选区或控制点微调 · Esc 取消": (
        "框选模式 · 拖动选区或控制点微调 · Esc 取消",
        "框選模式 · 拖曳選區或控制點微調 · Esc 取消",
        "Region mode · drag the selection or handles · Esc to cancel",
        "範囲モード · 選択範囲やハンドルをドラッグ · Esc で取消",
        "영역 모드 · 선택 영역이나 핸들을 드래그 · Esc 취소",
        "Mode zone · déplacez la sélection ou les poignées · Esc pour annuler",
        "Bereichsmodus · Auswahl oder Griffe ziehen · Esc zum Abbrechen",
        "Modo región · arrastra la selección o los tiradores · Esc para cancelar",
    ),
    "窗口模式 · 单击目标窗口确认 · Esc 取消": (
        "窗口模式 · 单击目标窗口确认 · Esc 取消",
        "視窗模式 · 按一下目標視窗確認 · Esc 取消",
        "Window mode · click the target window · Esc to cancel",
        "ウィンドウモード · 対象をクリックで確定 · Esc で取消",
        "창 모드 · 대상 창을 클릭하여 확인 · Esc 취소",
        "Mode fenêtre · cliquez la fenêtre cible · Esc pour annuler",
        "Fenstermodus · Zielfenster anklicken · Esc zum Abbrechen",
        "Modo ventana · clic en la ventana objetivo · Esc para cancelar",
    ),
    "全屏模式 · 已选中整块桌面 · 点确定继续": (
        "全屏模式 · 已选中整块桌面 · 点确定继续",
        "全螢幕模式 · 已選取整個桌面 · 按確定繼續",
        "Full screen · whole desktop selected · press OK",
        "全画面モード · デスクトップ全体を選択済み · 確定で続行",
        "전체 화면 모드 · 전체 데스크톱 선택됨 · 확인을 누르세요",
        "Plein écran · bureau entier sélectionné · validez",
        "Vollbild · gesamter Desktop gewählt · OK drücken",
        "Pantalla completa · escritorio seleccionado · pulsa OK",
    ),
    "边框线型": (
        "边框线型", "框線樣式", "Border line style", "枠線の種類",
        "테두리 선 스타일", "Style de la bordure", "Rahmenlinienstil",
        "Estilo del borde",
    ),

    # v39：主窗口 / 编辑器顶部按钮新增文案
    "最小化": (
        "最小化", "最小化", "Minimize", "最小化", "최소화",
        "Réduire", "Minimieren", "Minimizar",
    ),
    "最大化": (
        "最大化", "最大化", "Maximize", "最大化", "최대화",
        "Agrandir", "Maximieren", "Maximizar",
    ),
    "还原": (
        "还原", "還原", "Restore", "元に戻す", "복원",
        "Restaurer", "Wiederherstellen", "Restaurar",
    ),
    "关于": (
        "关于", "關於", "About", "概要", "정보",
        "À propos", "Info", "Acerca de",
    ),
    "版本信息 · 联系邮箱": (
        "版本信息 · 联系邮箱", "版本資訊 · 聯絡信箱", "Version info · contact email",
        "バージョン情報 · 連絡先メール", "버전 정보 · 문의 이메일",
        "Informations de version · e-mail de contact",
        "Versionsinfo · Kontakt-E-Mail", "Información de versión · correo de contacto",
    ),
    "托盘常驻 · 关闭窗口不会退出程序": (
        "托盘常驻 · 关闭窗口不会退出程序",
        "托盤常駐 · 關閉視窗不會結束程式",
        "Stays in tray · closing the window won't quit",
        "トレイ常駐 · ウィンドウを閉じても終了しません",
        "트레이 상주 · 창을 닫아도 종료되지 않습니다",
        "Resident dans la barre · fermer la fenêtre ne quitte pas l'application",
        "Im Infobereich · Fenster schließen beendet das Programm nicht",
        "Permanece en la bandeja · cerrar la ventana no sale del programa",
    ),

    # ------------------------------------------------------------ V52 录屏（K-recording UI）
    "录屏": (
        "录屏", "錄影", "Screen recording", "画面録画",
        "화면 녹화", "Enregistrement d'écran", "Bildschirmaufnahme", "Grabación de pantalla",
    ),
    "开始录屏": (
        "开始录屏", "開始錄影", "Start recording", "録画を開始",
        "녹화 시작", "Démarrer l'enregistrement", "Aufnahme starten", "Iniciar grabación",
    ),
    # V52.2：截图页底部大按钮（与「开始录屏」同款）
    "开始截图": (
        "开始截图", "開始截圖", "Start capture", "キャプチャを開始",
        "캡처 시작", "Démarrer la capture", "Aufnahme starten", "Iniciar captura",
    ),
    "停止": (
        "停止", "停止", "Stop", "停止",
        "중지", "Arrêter", "Stopp", "Detener",
    ),
    "已暂停 · F9 继续": (
        "已暂停 · F9 继续", "已暫停 · F9 繼續", "Paused · F9 to resume",
        "一時停止中 · F9 で再開", "일시정지 · F9 로 계속",
        "En pause · F9 pour reprendre", "Pausiert · F9 zum Fortsetzen", "En pausa · F9 para continuar",
    ),
    "⇥ 退出": (
        "⇥ 退出", "⇥ 結束", "⇥ Exit", "⇥ 終了",
        "⇥ 종료", "⇥ Quitter", "⇥ Beenden", "⇥ Salir",
    ),
    "录屏方式": (
        "录屏方式", "錄影方式", "Recording mode", "録画方法",
        "녹화 방식", "Mode d'enregistrement", "Aufnahme-Modus", "Modo de grabación",
    ),
    "声音与画面": (
        "声音与画面", "聲音與畫面", "Sound and picture", "音声と映像",
        "소리와 화면", "Son et image", "Ton und Bild", "Sonido e imagen",
    ),
    "录制设置": (
        "录制设置", "錄影設定", "Recording settings", "録画設定",
        "녹화 설정", "Paramètres d'enregistrement", "Aufnahme-Einstellungen", "Ajustes de grabación",
    ),
    "画面帧率": (
        "画面帧率", "畫面幀率", "Frame rate", "フレームレート",
        "프레임률", "Fréquence d'images", "Bildrate", "Velocidad de fotogramas",
    ),
    "越高越流畅 · 文件也越大": (
        "越高越流畅 · 文件也越大", "越高越流暢 · 檔案也越大", "Higher is smoother · larger file",
        "高いほど滑らか · ファイルも大きくなる", "높을수록 부드럽고 · 파일도 커집니다",
        "Plus élevé = plus fluide · fichier plus gros", "Höher = flüssiger · größere Datei",
        "Más alto = más fluido · archivo más grande",
    ),
    "保存位置": (
        "保存位置", "儲存位置", "Save location", "保存先",
        "저장 위치", "Emplacement d'enregistrement", "Speicherort", "Ubicación de guardado",
    ),
    "录屏热键": (
        "录屏热键", "錄影熱鍵", "Recording hotkey", "録画ホットキー",
        "녹화 단축키", "Raccourci d'enregistrement", "Aufnahme-Tastenkürzel", "Atajo de grabación",
    ),
    "录制完成的音频怎么存": (
        "录制完成的音频怎么存", "錄製完成的聲音怎麼存", "How to save the recorded audio",
        "録音した音声の保存方法", "녹음된 오디오 저장 방식",
        "Comment enregistrer l'audio capturé", "Audio-Speicherart nach Aufnahme",
        "Cómo guardar el audio grabado",
    ),
    "导出格式": (
        "导出格式", "匯出格式", "Export format", "書き出し形式",
        "내보내기 형식", "Format d'export", "Exportformat", "Formato de exportación",
    ),
    "GIF 无声 · 体积更小": (
        "GIF 无声 · 体积更小", "GIF 無聲 · 體積更小", "GIF silent · smaller file",
        "GIF は音声なし · ファイルが小さい", "GIF 무음 · 파일이 작음",
        "GIF sans son · fichier plus petit", "GIF stumm · kleinere Datei",
        "GIF sin sonido · archivo más pequeño",
    ),
    "点击修改，立即生效": (
        "点击修改，立即生效", "點擊修改，立即生效", "Click to change, applies immediately",
        "クリックで変更 · 即時反映", "클릭하여 변경 · 즉시 적용",
        "Cliquer pour modifier, effet immédiat", "Klicken zum Ändern, sofort wirksam",
        "Haga clic para cambiar, se aplica al instante",
    ),
    "已暂停 · {hk} 继续": (
        "已暂停 · {hk} 继续", "已暫停 · {hk} 繼續", "Paused · {hk} to resume",
        "一時停止中 · {hk} で再開", "일시정지 · {hk} 로 계속",
        "En pause · {hk} pour reprendre", "Pausiert · {hk} zum Fortsetzen",
        "En pausa · {hk} para continuar",
    ),
    "设置录屏热键 - {app}": (
        "设置录屏热键 - {app}", "設定錄影熱鍵 - {app}", "Set recording hotkey - {app}",
        "録画ホットキーの設定 - {app}", "녹화 단축키 설정 - {app}",
        "Raccourci d'enregistrement - {app}", "Aufnahme-Tastenkürzel - {app}",
        "Atajo de grabación - {app}",
    ),
    "录屏热键已改为 {label}": (
        "录屏热键已改为 {label}", "錄影熱鍵已改為 {label}", "Recording hotkey changed to {label}",
        "録画ホットキーを {label} に変更", "녹화 단축키가 {label}(으)로 변경됨",
        "Raccourci d'enregistrement changé en {label}", "Aufnahme-Tastenkürzel geändert zu {label}",
        "Atajo de grabación cambiado a {label}",
    ),
    "开始 / 停止录屏 ({label})": (
        "开始 / 停止录屏 ({label})", "開始 / 停止錄影 ({label})", "Start / stop recording ({label})",
        "録画の開始 / 停止 ({label})", "녹화 시작 / 중지 ({label})",
        "Démarrer / arrêter l'enregistrement ({label})", "Aufnahme starten / stoppen ({label})",
        "Iniciar / detener grabación ({label})",
    ),
    "选择录屏保存位置": (
        "选择录屏保存位置", "選擇錄影儲存位置", "Choose recording save location",
        "録画の保存先を選択", "녹화 저장 위치 선택",
        "Choisir l'emplacement d'enregistrement", "Aufnahme-Speicherort wählen",
        "Elegir ubicación de guardado",
    ),
    "保存位置未能写入配置": (
        "保存位置未能写入配置", "儲存位置未能寫入設定", "Could not save the location to config",
        "保存先を設定に書き込めませんでした", "저장 위치를 설정에 쓸 수 없습니다",
        "Impossible d'enregistrer l'emplacement", "Speicherort konnte nicht gespeichert werden",
        "No se pudo guardar la ubicación en la configuración",
    ),
    "录屏保存位置已设为 {path}": (
        "录屏保存位置已设为 {path}", "錄影儲存位置已設為 {path}", "Recording save location set to {path}",
        "録画の保存先を {path} に設定", "녹화 저장 위치가 {path}(으)로 설정됨",
        "Emplacement d'enregistrement défini sur {path}", "Aufnahme-Speicherort auf {path} gesetzt",
        "Ubicación de guardado establecida en {path}",
    ),
    "开始 / 停止都用它": (
        "开始 / 停止都用它", "開始 / 停止都用它", "Use it to start and stop",
        "開始 / 停止どちらにも使用", "시작 / 중지 모두 사용",
        "Utilisé pour démarrer et arrêter", "Für Start und Stopp verwenden", "Úselo para iniciar y detener",
    ),
    "含录屏操作文档": (
        "含录屏操作文档", "含錄影操作文件", "Includes screen recording guide",
        "画面録画の操作説明を含む", "화면 녹화 사용 설명 포함",
        "Includes the screen recording guide", "Enthält Anleitung zur Bildschirmaufnahme",
        "Incluye la guía de grabación de pantalla",
    ),
    "顶部切换「截图 / 录屏」 · 三种方式沿用同一套分栏": (
        "顶部切换「截图 / 录屏」 · 三种方式沿用同一套分栏",
        "頂部切換「截圖 / 錄影」 · 三種方式沿用同一套分欄",
        "Switch between Screenshot / Recording at the top · all three modes share the same layout",
        "上部で「スクリーンショット / 録画」を切り替え · 3 つの方式は同じレイアウト",
        "상단에서 캡처 / 녹화 전환 · 세 방식 모두 같은 분할 레이아웃 사용",
        "Basculez entre Capture / Enregistrement en haut · les trois modes partagent la même disposition",
        "Oben zwischen Screenshot / Aufnahme wechseln · alle drei Modi nutzen dasselbe Layout",
        "Cambia entre Captura / Grabación arriba · los tres modos usan el mismo diseño",
    ),
    "录制鼠标指针": (
        "录制鼠标指针", "錄製滑鼠指標", "Record mouse cursor", "マウスカーソルを録画",
        "마우스 커서 기록", "Enregistrer le curseur de la souris", "Mauszeiger aufnehmen",
        "Grabar el cursor del ratón",
    ),
    "视频里显示光标位置": (
        "视频里显示光标位置", "影片裡顯示游標位置", "Show cursor in the video",
        "動画にカーソルを表示", "동영상에 커서 표시",
        "Afficher le curseur dans la vidéo", "Cursor im Video anzeigen", "Mostrar el cursor en el vídeo",
    ),
    "系统声音": (
        "系统声音", "系統聲音", "System audio", "システム音声",
        "시스템 소리", "Son système", "Systemton", "Sonido del sistema",
    ),
    "系统声": (
        "系统声", "系統聲", "System sound", "システム音",
        "시스템 소리", "Son du système", "Systemton", "Sonido del sistema",
    ),
    "录电脑播放的声音": (
        "录电脑播放的声音", "錄電腦播放的聲音", "Record system audio",
        "コンピューターの音声を録音", "컴퓨터에서 나는 소리 녹음",
        "Enregistrer le son du système", "Systemton aufnehmen", "Grabar el sonido del sistema",
    ),
    "麦克风": (
        "麦克风", "麥克風", "Microphone", "マイク",
        "마이크", "Microphone", "Mikrofon", "Micrófono",
    ),
    "录你说话的声音": (
        "录你说话的声音", "錄你說話的聲音", "Record your voice", "自分の声を録音",
        "내 목소리 녹음", "Enregistrer votre voix", "Ihre Stimme aufnehmen", "Grabar tu voz",
    ),
    "摄像头画中画": (
        "摄像头画中画", "攝影機畫中畫", "Webcam picture-in-picture",
        "ウェブカメラのピクチャーインピクチャー", "웹캠 화중화 (PIP)",
        "Incrustation de la webcam", "Webcam-Bild-in-Bild", "Imagen en imagen de la webcam",
    ),
    "把摄像头画面贴到角落": (
        "把摄像头画面贴到角落", "把攝影機畫面貼到角落", "Overlay the webcam in a corner",
        "ウェブカメラ映像を隅に表示", "웹캠 화면을 모서리에 표시",
        "Afficher la webcam dans un coin", "Webcam-Bild in einer Ecke einblenden",
        "Mostrar la webcam en una esquina",
    ),
    "画中画位置": (
        "画中画位置", "畫中畫位置", "Picture-in-picture position",
        "ピクチャーインピクチャーの位置", "화중화 위치",
        "Position de l'incrustation", "Bild-in-Bild-Position", "Posición de la imagen en imagen",
    ),
    "角落位置": (
        "角落位置", "角落位置", "Corner position", "隅の位置",
        "모서리 위치", "Position dans le coin", "Eckenposition", "Posición de la esquina",
    ),
    "画中画大小": (
        "画中画大小", "畫中畫大小", "Picture-in-picture size",
        "ピクチャーインピクチャーのサイズ", "화중화 크기",
        "Taille de l'incrustation", "Bild-in-Bild-Größe", "Tamaño de la imagen en imagen",
    ),
    "占画面宽度比例": (
        "占画面宽度比例", "佔畫面寬度比例", "Share of screen width", "画面幅に占める割合",
        "화면 너비 비율", "Part de la largeur de l'écran", "Anteil der Bildschirmbreite",
        "Porcentaje del ancho de pantalla",
    ),
    "音频保存": (
        "音频保存", "音訊儲存", "Audio saving", "音声の保存",
        "오디오 저장", "Enregistrement de l'audio", "Audio-Speicherung", "Guardado de audio",
    ),
    "每次录制前再确认一次": (
        "每次录制前再确认一次", "每次錄影前再確認一次", "Ask again before every recording",
        "録画のたびに確認する", "녹화할 때마다 다시 확인",
        "Demander à nouveau avant chaque enregistrement", "Vor jeder Aufnahme erneut nachfragen",
        "Preguntar de nuevo antes de cada grabación",
    ),
    "整合到视频里（推荐）：声音嵌进 MP4，只有一个文件": (
        "整合到视频里（推荐）：声音嵌进 MP4，只有一个文件",
        "整合到影片裡（推薦）：聲音嵌進 MP4，只有一個檔案",
        "Embed in video (recommended): audio inside the MP4, a single file",
        "動画に統合（推奨）：音声を MP4 に埋め込み、ファイルは 1 つ",
        "동영상에 포함 (권장): 오디오를 MP4 에 넣어 파일 하나로 저장",
        "Intégré à la vidéo (recommandé) : son dans le MP4, un seul fichier",
        "Ins Video integriert (empfohlen): Ton in der MP4, nur eine Datei",
        "Integrado en el vídeo (recomendado): audio dentro del MP4, un solo archivo",
    ),
    "分开保存：视频不带声音，声音单独存成 WAV 文件": (
        "分开保存：视频不带声音，声音单独存成 WAV 文件",
        "分開儲存：影片不含聲音，聲音單獨存成 WAV 檔案",
        "Separate: video without sound, audio saved as a WAV file",
        "別々に保存：動画は音声なし、音声は WAV ファイルとして保存",
        "분리 저장: 동영상은 소리 없이, 소리는 WAV 파일로 저장",
        "Séparer : vidéo sans son, audio enregistré dans un fichier WAV",
        "Getrennt: Video ohne Ton, Audio als WAV-Datei speichern",
        "Separado: vídeo sin sonido, audio guardado como archivo WAV",
    ),
    "两者都要：视频里有声音，同时单独导出 WAV 文件": (
        "两者都要：视频里有声音，同时单独导出 WAV 文件",
        "兩者都要：影片裡有聲音，同時單獨匯出 WAV 檔案",
        "Both: sound in the video plus a separate WAV file",
        "両方：動画に音声を含めつつ、WAV ファイルも別途書き出す",
        "둘 다: 동영상에 소리를 넣고 WAV 파일도 따로 내보내기",
        "Les deux : son dans la vidéo et fichier WAV séparé",
        "Beides: Ton im Video und zusätzliche WAV-Datei",
        "Ambos: sonido en el vídeo y archivo WAV por separado",
    ),
    "开始 / 停止录屏 (F9)": (
        "开始 / 停止录屏 (F9)", "開始 / 停止錄影 (F9)", "Start / Stop recording (F9)",
        "録画開始 / 停止 (F9)", "녹화 시작 / 중지 (F9)",
        "Démarrer / Arrêter l'enregistrement (F9)", "Aufnahme starten / stoppen (F9)",
        "Iniciar / Detener grabación (F9)",
    ),
    "录屏已保存：{path}": (
        "录屏已保存：{path}", "錄影已儲存：{path}", "Recording saved: {path}",
        "録画を保存しました: {path}", "녹화 저장됨: {path}",
        "Enregistrement enregistré : {path}", "Aufnahme gespeichert: {path}",
        "Grabación guardada: {path}",
    ),
    "请选择这一次录制里，声音要怎么保存：": (
        "请选择这一次录制里，声音要怎么保存：", "請選擇這一次錄影裡，聲音要怎麼儲存：",
        "Choose how to save audio for this recording:",
        "今回の録画の音声の保存方法を選択してください：",
        "이번 녹화에서 소리를 저장할 방식을 선택하세요:",
        "Choisissez comment enregistrer l'audio pour cet enregistrement :",
        "Wählen Sie, wie das Audio dieser Aufnahme gespeichert wird:",
        "Elige cómo guardar el audio de esta grabación:",
    ),
    "本次录制的音频怎么保存？": (
        "本次录制的音频怎么保存？", "這次的音訊要怎麼儲存？",
        "How should this recording's audio be saved?",
        "今回の録音の音声はどう保存しますか？", "이번 녹화의 오디오는 어떻게 저장할까요?",
        "Comment enregistrer l'audio de cet enregistrement ?",
        "Wie soll das Audio dieser Aufnahme gespeichert werden?",
        "¿Cómo guardar el audio de esta grabación?",
    ),
    "视频里的音轨方式：": (
        "视频里的音轨方式：", "影片裡的音軌方式：", "Audio track mode in the video:",
        "動画の音声トラックの方法：", "동영상 오디오 트랙 방식:",
        "Mode de piste audio dans la vidéo :", "Audio-Spur-Modus im Video:",
        "Modo de pista de audio en el vídeo:",
    ),
    "提示：只勾选了系统声音或麦克风其中一路时，两种音轨方式效果相同。": (
        "提示：只勾选了系统声音或麦克风其中一路时，两种音轨方式效果相同。",
        "提示：只勾選系統聲音或麥克風其中一路時，兩種音軌方式效果相同。",
        "Tip: when only system audio or the microphone is enabled, both audio modes have the same effect.",
        "ヒント：システム音声またはマイクのどちらか一方のみを選択した場合、どちらの音声モードでも結果は同じです。",
        "팁: 시스템 소리 또는 마이크 중 하나만 선택하면 두 오디오 방식의 결과가 같습니다.",
        "Astuce : si seul le son système ou le micro est activé, les deux modes audio donnent le même résultat.",
        "Tipp: Wenn nur Systemton oder nur das Mikrofon aktiviert ist, sind beide Audio-Modi gleich.",
        "Consejo: si solo se activa el sonido del sistema o el micrófono, ambos modos de audio dan el mismo resultado.",
    ),

})


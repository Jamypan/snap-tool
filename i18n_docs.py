# -*- coding: utf-8 -*-
"""i18n_docs.py —— 帮助 / 命令行说明 / 关于的长文本多语言版本。

简体中文保留项目原有的完整详细文档（snapui.py 的 HELP_HTML / CLI_HELP /
ABOUT_HTML）；其它 7 种语言提供覆盖同样 8 个章节的说明。所有语言共用一个
渲染函数，切换语言时帮助窗口重新 setHtml 即可。
"""
from __future__ import annotations

from html import escape

from i18n import LANG, t

_CSS = """
<style>
body { font-family: 'Microsoft YaHei', sans-serif; font-size: 13px; color:#1f2937; }
h2 { color:#0a6ed1; font-size:16px; margin:16px 0 6px 0; }
p, li { line-height:1.6; }
table { border-collapse:collapse; width:100%; margin:6px 0; }
td, th { border:1px solid #d1d5db; padding:5px 8px; text-align:left; }
th { background:#f3f4f6; }
code { background:#f3f4f6; padding:1px 4px; }
.hint { color:#6b7280; }
</style>
"""

# 每个语言 8 个章节：(标题, 正文 HTML 片段)
_HELP: dict[str, tuple[tuple[str, str], ...]] = {
    "en": (
        ("1. Startup, floating bar and tray", "<p>On startup a slim <b>floating bar</b> appears at the bottom center of the screen, and a tray icon stays resident. From left to right: the orange logo, the three mode buttons (Area / Window / Full screen, the active one dark with an orange dot), Scrolling Capture, Pin, the current hotkey hint and &hellip;. <b>Closing the bar only sends it back to the tray</b>; use &hellip; &rarr; Help &rarr; About and Exit or the tray menu to quit. Drag an empty part of the bar to move it; right-click the tray icon to bring it back, left-click to capture.</p><p>&hellip; opens a <b>two-column command panel</b> (Capture / Edit and output on the left, Settings / Help on the right, 15 rows). Each row shows an icon, a title with a description and its current value or shortcut &mdash; <b>smoothing, default mode, interface language and hotkeys can all be switched right in the panel</b> and take effect immediately.</p>"),
        ("2. Capture modes", "<table><tr><th>Mode</th><th>How to use</th><th>Best for</th></tr><tr><td>Area</td><td>Drag a rectangle, then move it or adjust the eight handles</td><td>Part of the screen (default)</td></tr><tr><td>Window</td><td>Hover to highlight a window and click; right-click or Esc cancels</td><td>A whole window without the transparent shadow border</td></tr><tr><td>Full screen</td><td>The entire virtual screen is selected automatically</td><td>Desktop or multi-monitor setups</td></tr></table><p class=\"hint\">The app hides all of its own windows before capturing so they never appear in the shot. <b>A confirmation bar floats just outside the selection</b>: Copy, Text Extraction, Pin, &#10005; and the dark <b>OK</b> button that opens the editor; the strip at the top of the overlay switches modes in place.</p>"),
        ("3. Global hotkey", "<p>Default <b>Ctrl + Shift + A</b>. The mode used is the Default Mode in the command panel (remembered; the active mode is dark with an orange dot). Change it under Settings &rarr; Set Hotkey by pressing the combination directly or picking modifiers plus a main key. At least one of Ctrl / Alt / Shift / Win is required. If registration fails the combination is taken by another app. Saved in <code>%APPDATA%\\SnapTool\\settings.json</code>.</p>"),
        ("4. Editing a capture", "<table><tr><th>Action</th><th>Details</th></tr><tr><td>Annotate</td><td>Rectangle, ellipse, arrow, line, pen, mosaic, text</td></tr><tr><td>Style</td><td>Select a shape to open the style panel: color, width, line style, fill, font size, bold, text background, endpoint arrows</td></tr><tr><td>Transform</td><td>Rotate 90&deg; (Ctrl+R / Ctrl+Shift+R), flip horizontally (Ctrl+H) or vertically (Ctrl+Shift+H); image and annotations move together, Ctrl+Z undoes</td></tr><tr><td>Output</td><td>Enter / Copy, Ctrl+S / Save, Esc / Cancel; Scrolling Capture is a separate command (see section 9)</td></tr></table><p class=\"hint\">Ctrl + mouse wheel zooms the view (View menu: Zoom In / Out, Actual Size 1:1, Fit to Window); middle-drag pans the canvas. Zoom changes only the display, exports keep full resolution. A transparent line color makes borderless shapes, and closed shapes have a Fill opacity slider.</p><p class=\"hint\">Mosaic has no adjustable style: the style panel never opens while the Mosaic tool is active or a mosaic is selected.</p><p class=\"hint\">Select a rectangle or ellipse to show four <b>corner handles</b>: drag any corner to change width, height and shape. The opposite corner stays fixed, dragging past it flips the shape, and a minimum size is kept. Works in the overlay and in the editor window; handles keep their size when the view is zoomed.</p><p class=\"hint\">Select a rectangle, ellipse or text annotation to show a <b>rotation handle</b> above it: drag to rotate freely around its center, hold Shift to snap to 15&deg;, or set an exact angle with the Rotation angle slider in the style panel. Edit &rarr; Rotate Selected Shape gives 90&deg; steps (Ctrl+[ / Ctrl+]). Rotating the whole image now rotates text with it; exports always keep full resolution.</p><p class='hint'>Select a text annotation to give its <b>background</b> the same controls as a shape fill: preset swatches plus its own <b>Background opacity</b> slider (0&ndash;100%). Shape fill and text background keep their colors and opacities independently. Enable <b>Text background border</b> to outline the rounded background: pick a <b>Border color</b> (the ∅ swatch is fully transparent, i.e. no visible border) and set its own width and line style (solid / dashed / dotted). Background and border can be toggled separately, and both rotate together with the text.</p><p class='hint'>Text stays exactly where you typed it: the input box and the final annotation share the same baseline, including zoomed views and high-DPI screens.</p><p class='hint'>After selecting an area, the <b>Copy</b> button at the far left of the toolbar puts the original image on the clipboard and closes the overlay without opening the editor. Full-screen captures and long screenshots are copied automatically when finished.</p>"),
        ("5. Text extraction (OCR)", "<p>Use Text Extraction in the confirmation bar outside the selection, the editor dock, or Edit &rarr; OCR Text. Each recognized line is placed back over the original position: select, drag, Ctrl+A / Ctrl+C to copy, or use Copy Selection / Copy All in the top bar. The layer closes automatically after copying; Back or Esc only closes the layer. The bundled RapidOCR (ONNX) loads in 1-5 seconds on first use and is cached afterwards.</p>"),
        ("6. Files and configuration", "<p>Screenshots are saved to <code>%USERPROFILE%\\Pictures\\Screenshots</code> (shown in the command panel's Open Save Folder row, which opens it; the tray menu has the same item). Settings live in <code>%APPDATA%\\SnapTool\\settings.json</code>; set <code>SNAPTOOL_HOME</code> to relocate the config directory for portable use.</p>"),
        ("7. Command line", "<p><code>python snap.py --help</code> lists all options; <code>--shot</code> captures once on startup; <code>--restart</code> cleans up a stale background instance and restarts; <code>--selftest</code> verifies the OCR backend. Also under &hellip; &rarr; Help &rarr; Command Line.</p>"),
        ("8. Troubleshooting", "<ul><li><b>Hotkey does nothing:</b> another app owns the combination. Change it in Set Hotkey or click Area on the floating bar.</li><li><b>\"Already running\" but no window:</b> the tray icon may be in the notification overflow; a stale background instance can be replaced by choosing Yes in the prompt or running restart.bat.</li><li><b>Code changes not visible:</b> the old tray process is still running; restart.bat starts the new code.</li><li><b>Scaling offsets:</b> per-monitor DPI awareness is enabled; restart the app if coordinates look wrong.</li><li><b>Antivirus warning:</b> global hotkeys plus screen capture are often flagged; trust the unsigned exe.</li></ul>"),
        ("9. Scrolling Capture", "<p><b>Scrolling Capture</b> is a separate command alongside the three capture modes. Start it from the Scrolling Capture button on the floating bar, the command panel, or the tray menu. It <b>does not open the editor and needs no drag-selection</b>: <b>click a window and it starts scrolling down automatically</b>.</p><ol><li>All app windows are hidden first, then a full-screen overlay appears.</li><li>Move the mouse: the target window is highlighted with its title. <b>Left-click to select it</b> — the app uses its client area (title bar and borders excluded) as the scrolling region and <b>immediately</b> starts grabbing frames and stitching them by template matching.</li><li>While scrolling: <b>left-click pauses, click again to resume</b>; <b>right-click finishes</b>; click <b>Done ✓</b> in the floating bar or press Esc to finish; reaching the bottom <b>finishes automatically</b>.</li><li>A preview window opens when finished; save as PNG / JPG.</li></ol><p class='hint'>Captures tolerate slow pages: a single frame with almost no movement is re-checked instead of ending, failed alignment is retried with a smaller step, templates come from the middle of the frame to skip sticky headers, and the cursor is locked to the target window before each wheel event. The control bar shows the match score and the tray message reports frame count and why the capture ended.</p><p class='hint'>Own windows stay hidden during stitching and the control bar is placed outside the window (or briefly hidden while grabbing if the window fills the screen). Fixed floating elements or animations may prevent alignment.</p>"),
    ),
    "ja": (
        ("1. 起動とフローティング バー", "<p>起動すると画面下部中央に細い<b>フローティング バー</b>が表示され、トレイアイコンも常駐します。左からオレンジのロゴ、3 つのモード ボタン（範囲 / ウィンドウ / 全画面、選択中は濃色地にオレンジの点）、スクロール キャプチャ、ピン留め、現在のショートカット表示、「…」です。<b>バーを閉じてもトレイに戻るだけで終了しません</b>。終了は「… → ヘルプ → バージョン情報と終了」またはトレイメニューから。バーの余白をドラッグすると移動でき、トレイ右クリックで呼び戻せます。</p><p>「…」を押すと<b>2 列のコマンド パネル</b>（左が「キャプチャ / 編集と出力」、右が「設定 / ヘルプ」、全 15 行）が開きます。各行はアイコン、タイトルと説明、右側に現在の値またはショートカットを表示し、<b>スムーズさ・既定のモード・表示言語・ショートカットはパネル内でその場で切り替え</b>でき、すぐ反映されます。</p>"),
        ("2. 3 つのキャプチャ モード", "<table><tr><th>モード</th><th>操作</th><th>用途</th></tr><tr><td>範囲</td><td>ドラッグで矩形を選択、8 つのハンドルで微調整</td><td>画面の一部（既定）</td></tr><tr><td>ウィンドウ</td><td>カーソルを合わせてハイライトしクリック。右クリック / Esc で取消</td><td>影の枠を除いたウィンドウ全体</td></tr><tr><td>全画面</td><td>仮想画面全体を自動選択</td><td>デスクトップ / 複数モニター</td></tr></table><p class=\"hint\">撮影前にアプリ自身のウィンドウはすべて隠れるため、画像に写りません。<b>選択範囲の外側に確認バー</b>が浮かび、コピー / 文字抽出 / ピン留め / &#10005; / 濃色の<b>OK</b>（エディタを開く）が並びます。オーバーレイ上部のモード バーでその場でモードを切り替えられます。</p>"),
        ("3. グローバル ショートカット", "<p>既定は <b>Ctrl + Shift + A</b>。使用するモードはコマンド パネルの「既定のモード」（記憶されます。選択中のモードは濃色地にオレンジの点で表示）。「設定 → ショートカット設定」で直接キーを押すか、修飾キーと主キーを選んで変更できます。Ctrl / Alt / Shift / Win のいずれかが必須です。登録できない場合は他アプリと競合しています。設定は <code>%APPDATA%\\SnapTool\\settings.json</code> に保存されます。</p>"),
        ("4. キャプチャの編集", "<table><tr><th>操作</th><th>内容</th></tr><tr><td>注釈</td><td>四角形、楕円、矢印、直線、ペン、モザイク、テキスト</td></tr><tr><td>スタイル</td><td>図形を選択すると色・太さ・線種・塗りつぶし・文字サイズ・太字・背景色・端点矢印を変更</td></tr><tr><td>変換</td><td>90&deg; 回転 (Ctrl+R / Ctrl+Shift+R)、左右反転 (Ctrl+H)、上下反転 (Ctrl+Shift+H)。画像と注釈が一緒に変わり、Ctrl+Z で元に戻せます</td></tr><tr><td>出力</td><td>Enter / コピー、Ctrl+S / 保存、Esc / キャンセル。スクロール キャプチャは独立コマンドです（第 9 節参照）</td></tr></table><p class=\"hint\">Ctrl + ホイールで表示を拡大縮小（表示メニューに拡大・縮小・等倍 1:1・ウィンドウに合わせる）。中ボタンドラッグで移動でき、書き出しは元の解像度のままです。線色の「透明」で枠線なしの図形、塗りつぶしには不透明度スライダーがあります。</p><p class=\"hint\">モザイクには調整できるスタイルがありません。モザイク ツールの使用中やモザイクを選択している間は、スタイル パネルは開きません。</p><p class=\"hint\">四角形・楕円を選択すると<b>四隅のハンドル</b>が表示されます。任意の隅をドラッグして幅・高さ・形状を変更できます（対角は固定、反対側までドラッグすると反転、最小サイズを保持）。オーバーレイと編集ウィンドウの両方で使え、表示を拡大してもハンドルの大きさは変わりません。</p><p class=\"hint\">四角形・楕円・テキストを選択すると上部に<b>回転ハンドル</b>が表示され、ドラッグで中心を軸に自由に回転できます（Shift で 15&deg; 単位にスナップ、スタイル パネルの「回転角度」で数値指定も可能）。編集 &rarr; 選択中の図形を回転 で 90&deg; ずつ回転（Ctrl+[ / Ctrl+]）。画像全体を回転すると文字も一緒に回転します。書き出しは常に元の解像度です。</p><p class='hint'>テキストを選択すると、<b>背景色</b>に図形の塗りつぶしと同じ操作（プリセット色＋専用の<b>背景の不透明度</b>スライダー 0〜100%）が使えます。図形の塗りつぶしと文字背景の色・不透明度はそれぞれ別に記憶されます。<b>文字背景の枠線</b>を有効にすると角丸背景に枠線を描け、<b>枠線の色</b>（∅ は完全に透明＝枠線なし）、専用の太さと線種（実線／破線／点線）を設定できます。背景と枠線は個別に切り替えられ、文字の回転に合わせて一緒に回転します。</p><p class='hint'>文字は入力した位置から動きません。入力ボックスと確定後の文字は同じベースラインで描画され、表示の拡大・縮小や高 DPI 画面でも位置がずれません。</p><p class='hint'>範囲を確定すると、ツールバー左端の「コピー」ボタンで元画像をクリップボードにコピーして遮罩を閉じます。編集ウィンドウは開きません。全画面キャプチャと長スクリーンショットは完了時に自動でコピーされます。</p>"),
        ("5. 文字抽出（OCR）", "<p>選択範囲の外側に浮かぶ確認バーの「文字抽出」、エディタ下部の Dock、または「編集 → OCR 文字抽出」から使います。認識した各行を元の位置に重ねて表示し、選択・ドラッグ・Ctrl+A / Ctrl+C でコピーできます。上部バーの「選択範囲をコピー」「すべてコピー」も利用可能。コピー後は自動的に閉じ、「戻る」または Esc でレイヤーだけ閉じます。同梱の RapidOCR (ONNX) は初回のみ 1〜5 秒で読み込み、以降はキャッシュされます。</p>"),
        ("6. ファイルと設定", "<p>画像は <code>%USERPROFILE%\\Pictures\\Screenshots</code> に保存（コマンド パネルの「保存フォルダーを開く」行に実際のパスが表示され、クリックで開きます。トレイにも同じ項目があります）。設定は <code>%APPDATA%\\SnapTool\\settings.json</code>。環境変数 <code>SNAPTOOL_HOME</code> で設定先を変更できます。</p>"),
        ("7. コマンドライン", "<p><code>python snap.py --help</code> で全オプションを表示。<code>--shot</code> は起動直後に 1 回撮影、<code>--restart</code> は残存プロセスを整理して再起動、<code>--selftest</code> は OCR バックエンドを検証します。「… → ヘルプ → コマンドライン」からも参照できます。</p>"),
        ("8. トラブルシューティング", "<ul><li><b>ショートカットが効かない：</b>他アプリと競合しています。設定で変更するか、フローティング バーの「範囲」ボタンから撮影してください。</li><li><b>「実行中」なのにウィンドウが無い：</b>トレイの折りたたみを確認するか、確認画面で「はい」を選んで再起動（restart.bat でも可）。</li><li><b>変更が反映されない：</b>旧プロセスが常駐しています。restart.bat で再起動を。</li><li><b>座標がずれる：</b>モニター別 DPI は有効です。再起動してお試しください。</li><li><b>ウイルス警告：</b>ホットキーと画面キャプチャは誤検知されやすい機能です。未署名 exe を信頼設定に追加してください。</li></ul>"),
        ("9. スクロール キャプチャ", "<p><b>スクロール キャプチャ</b>は 3 つのキャプチャ モードとは別の独立コマンドです。フローティング バーのスクロール キャプチャ ボタン、コマンド パネル、トレイメニューから起動します。<b>エディタは開かず、ドラッグ選択も不要</b>です。<b>ウィンドウをクリックすると自動的に下へスクロール</b>します。</p><ol><li>先にアプリの全ウィンドウを隠し、全画面オーバーレイを表示します。</li><li>マウスを動かすと対象ウィンドウがタイトル付きで強調表示されます。<b>左クリックで選択</b>すると、クライアント領域（タイトルバーと枠を除く）をスクロール範囲として<b>直ちに</b>フレーム取得とテンプレート照合による結合を開始します。</li><li>スクロール中：<b>左クリックで一時停止、もう一度クリックで再開</b>。<b>右クリックで終了</b>。フローティングバーの「<b>完了 ✓</b>」または Esc でも終了します。最下部に到達すると<b>自動終了</b>します。</li><li>完了するとプレビューが開き、PNG / JPG で保存できます。</li></ol><p class='hint'>途中終了を減らすため、1 フレームだけ動かなかった場合は再確認し、位置合わせ失敗は小さいステップで再試行、テンプレートは固定ヘッダーを避けて画面中央から取得し、毎回カーソルを対象ウィンドウに戻します。制御バーに一致度を表示し、終了時はトレイにフレーム数と終了理由を通知します。</p><p class='hint'>結合中は自ウィンドウを隠したままにし、制御バーはウィンドウの外に配置します（画面いっぱいの場合は取得瞬間だけ一時非表示）。固定された浮遊要素やアニメーションがあると位置合わせできない場合があります。</p>"),
    ),
    "ko": (
        ("1. 시작과 플로팅 바", "<p>시작하면 화면 아래쪽 중앙에 얇은 <b>플로팅 바</b>가 나타나고 트레이 아이콘도 상주합니다. 왼쪽부터 주황색 로고, 세 가지 모드 버튼(영역 / 창 / 전체 화면, 선택된 것은 어두운 배경에 주황 점), 스크롤 캡처, 고정, 현재 단축키 표시, '…' 순서입니다. <b>바를 닫아도 트레이로 돌아갈 뿐 종료되지 않습니다</b>. 종료는 '… → 도움말 → 정보 및 종료' 또는 트레이 메뉴를 사용하세요. 바의 빈 곳을 드래그해 옮길 수 있고 트레이 오른쪽 클릭으로 다시 부를 수 있습니다.</p><p>'…'를 누르면 <b>2열 명령 패널</b>(왼쪽 '캡처 / 편집 및 출력', 오른쪽 '설정 / 도움말', 총 15행)이 열립니다. 각 행은 아이콘, 제목과 설명, 오른쪽에 현재 값 또는 단축키를 보여 주며 <b>부드러움·기본 모드·언어·단축키를 패널에서 바로 전환</b>할 수 있고 즉시 적용됩니다.</p>"),
        ("2. 세 가지 캡처 모드", "<table><tr><th>모드</th><th>사용법</th><th>적합한 경우</th></tr><tr><td>영역</td><td>드래그로 사각형 선택 후 8개 핸들로 미세 조정</td><td>화면 일부(기본값)</td></tr><tr><td>창</td><td>창 위에 마우스를 올려 강조하고 클릭, 오른쪽 클릭 / Esc로 취소</td><td>투명 그림자 테두리를 제외한 창 전체</td></tr><tr><td>전체 화면</td><td>가상 화면 전체 자동 선택</td><td>바탕화면 / 멀티 모니터</td></tr></table><p class=\"hint\">촬영 전에 앱의 모든 창이 숨겨지므로 사진에 찍히지 않습니다. <b>선택 영역 바깥에 확인 바</b>가 떠서 복사 / 문자 인식 / 고정 / &#10005; / 어두운 <b>확인</b>(편집기 열기) 버튼이 놓이며, 오버레이 위쪽의 모드 바에서 그 자리에서 모드를 바꿀 수 있습니다.</p>"),
        ("3. 전역 단축키", "<p>기본값 <b>Ctrl + Shift + A</b>. 사용 모드는 명령 패널의 '기본 모드'이며 저장됩니다(선택된 모드는 어두운 배경에 주황 점으로 표시). 설정 → 단축키 설정에서 조합을 직접 누르거나 보조 키와 기본 키를 선택해 변경할 수 있습니다. Ctrl / Alt / Shift / Win 중 하나 이상이 필요합니다. 등록 실패 시 다른 앱이 사용 중입니다. 설정은 <code>%APPDATA%\\SnapTool\\settings.json</code>에 저장됩니다.</p>"),
        ("4. 캡처 편집", "<table><tr><th>동작</th><th>설명</th></tr><tr><td>주석</td><td>사각형, 타원, 화살표, 직선, 펜, 모자이크, 텍스트</td></tr><tr><td>스타일</td><td>도형 선택 시 색상, 두께, 선 스타일, 채우기, 글자 크기, 굵게, 배경색, 끝점 화살표 변경</td></tr><tr><td>변환</td><td>90&deg; 회전 (Ctrl+R / Ctrl+Shift+R), 좌우 반전 (Ctrl+H), 상하 반전 (Ctrl+Shift+H). 이미지와 주석이 함께 변하고 Ctrl+Z로 되돌릴 수 있습니다</td></tr><tr><td>출력</td><td>Enter / 복사, Ctrl+S / 저장, Esc / 취소. 스크롤 캡처는 별도 명령입니다(9절 참조)</td></tr></table><p class=\"hint\">Ctrl + 휠로 보기를 확대/축소합니다(보기 메뉴: 확대, 축소, 실제 크기 1:1, 창에 맞춤). 가운데 버튼 드래그로 이동하며 내보내기는 원본 해상도를 유지합니다. 선 색상의 투명 옵션으로 테두리 없는 도형을 그리고, 채우기에는 불투명도 슬라이더가 있습니다.</p><p class=\"hint\">모자이크에는 조정할 스타일이 없습니다. 모자이크 도구가 활성화되어 있거나 모자이크를 선택한 동안에는 스타일 패널이 열리지 않습니다.</p><p class=\"hint\">사각형이나 타원을 선택하면 <b>모서리 핸들</b> 네 개가 나타납니다. 아무 모서리나 드래그해 너비·높이·모양을 바꿀 수 있으며 반대쪽 모서리는 고정되고, 그 너머로 드래그하면 뒤집히고 최소 크기가 유지됩니다. 오버레이와 편집 창 모두에서 사용할 수 있고 화면을 확대해도 핸들 크기는 그대로입니다.</p><p class=\"hint\">사각형·타원·텍스트를 선택하면 위쪽에 <b>회전 핸들</b>이 나타나며, 드래그해 중심을 기준으로 자유롭게 회전할 수 있습니다(Shift로 15&deg; 단위 스냅, 스타일 패널의 회전 각도 슬라이더로 정확한 값 지정 가능). 편집 &rarr; 선택한 도형 회전 메뉴로 90&deg; 단계 회전(Ctrl+[ / Ctrl+]). 이미지 전체를 회전하면 텍스트도 함께 회전합니다. 내보내기는 항상 원본 해상도입니다.</p><p class='hint'>텍스트를 선택하면 <b>배경색</b>에 도형 채우기와 같은 조작(프리셋 색상 + 전용 <b>배경 불투명도</b> 슬라이더 0~100%)을 사용할 수 있습니다. 두 불투명도는 각각 따로 저장됩니다. <b>텍스트 배경 테두리</b>를 켜면 둥근 배경에 테두리를 그리며, <b>테두리 색상</b>(∅ 는 완전 투명 = 테두리 없음), 전용 두께와 선 스타일(실선/파선/점선)을 설정할 수 있습니다. 배경과 테두리는 각각 켜고 끌 수 있고 텍스트 회전을 따라 함께 회전합니다.</p><p class='hint'>텍스트는 입력한 위치에서 움직이지 않습니다. 입력 상자와 최종 글자가 같은 기준선을 공유하며, 화면 확대/축소 및 고 DPI에서도 위치가 어긋나지 않습니다.</p><p class='hint'>영역을 확정하면 도구 모음 맨 왼쪽의 <b>복사</b> 버튼이 원본 이미지를 클립보드에 넣고 편집 창을 열지 않고 오버레이를 닫습니다. 전체 화면 캡처와 스크롤 캡처는 완료 시 자동으로 복사됩니다.</p>"),
        ("5. 문자 추출(OCR)", "<p>선택 영역 바깥 확인 바의 '문자 인식', 편집기 하단 Dock, 또는 편집 → OCR 문자 추출에서 사용하세요. 인식된 각 줄을 원래 위치에 덮어 표시하며 선택, 드래그, Ctrl+A / Ctrl+C로 복사할 수 있습니다. 상단 바의 '선택 영역 복사' '전체 복사'도 사용 가능합니다. 복사 후 자동으로 닫히고, '돌아가기' 또는 Esc는 레이어만 닫습니다. 내장 RapidOCR(ONNX)은 처음 한 번 1~5초 로드된 뒤 캐시됩니다.</p>"),
        ("6. 파일 및 설정", "<p>스크린샷은 <code>%USERPROFILE%\\Pictures\\Screenshots</code>에 저장됩니다(명령 패널의 '저장 폴더 열기' 행에 실제 경로가 표시되고 클릭하면 열립니다. 트레이에도 같은 항목이 있습니다). 설정은 <code>%APPDATA%\\SnapTool\\settings.json</code>이며 <code>SNAPTOOL_HOME</code>으로 위치를 바꿀 수 있습니다.</p>"),
        ("7. 명령줄", "<p><code>python snap.py --help</code>로 전체 옵션 확인. <code>--shot</code>은 시작 후 한 번 캡처, <code>--restart</code>는 잔여 인스턴스를 정리 후 재시작, <code>--selftest</code>는 OCR 백엔드를 검증합니다. '… → 도움말 → 명령줄 옵션'에서도 볼 수 있습니다.</p>"),
        ("8. 문제 해결", "<ul><li><b>단축키가 동작하지 않음:</b> 다른 앱이 조합을 사용 중입니다. 설정에서 바꾸거나 플로팅 바의 '영역' 버튼을 누르세요.</li><li><b>'실행 중'인데 창이 없음:</b> 트레이 접힘 영역을 확인하거나 확인 창에서 '예'를 선택해 재시작하세요(restart.bat도 가능).</li><li><b>변경이 반영되지 않음:</b> 이전 프로세스가 상주 중입니다. restart.bat으로 재시작하세요.</li><li><b>좌표가 어긋남:</b> 모니터별 DPI 인식이 적용되어 있습니다. 재시작 후 확인하세요.</li><li><b>백신 오탐:</b> 전역 단축키와 화면 캡처는 오탐되기 쉽습니다. 서명 없는 exe를 신뢰 목록에 추가하세요.</li></ul>"),
        ("9. 스크롤 캡처", "<p><b>스크롤 캡처</b>는 세 가지 캡처 모드와 별개인 독립 명령입니다. 플로팅 바의 스크롤 캡처 버튼, 명령 패널, 트레이 메뉴에서 실행하며 <b>편집기를 열지 않고 드래그 선택도 필요 없습니다</b>. <b>창을 클릭하면 자동으로 아래로 스크롤</b>합니다.</p><ol><li>먼저 앱의 모든 창을 숨기고 전체 화면 오버레이를 표시합니다.</li><li>마우스를 움직이면 대상 창이 제목과 함께 강조됩니다. <b>왼쪽 클릭으로 선택</b>하면 클라이언트 영역(제목 표시줄과 테두리 제외)을 스크롤 범위로 삼아 <b>즉시</b> 프레임 캡처와 템플릿 매칭 결합을 시작합니다.</li><li>스크롤 중: <b>왼쪽 클릭은 일시 정지, 다시 클릭하면 계속</b>. <b>오른쪽 클릭은 종료</b>. 떠 있는 제어 막대의 「<b>완료 ✓</b>」 또는 Esc 로도 종료하며, 맨 아래에 도달하면 <b>자동 종료</b>됩니다.</li><li>완료되면 미리보기가 열리며 PNG / JPG 로 저장할 수 있습니다.</li></ol><p class='hint'>중도 종료를 줄이기 위해 한 프레임만 움직이지 않으면 재확인하고, 정렬 실패는 더 작은 간격으로 재시도하며, 고정 헤더를 피해 화면 중앙에서 템플릿을 추출하고 매번 커서를 대상 창으로 되돌립니다. 제어 막대에 일치도를 표시하고 종료 시 트레이에 프레임 수와 종료 이유를 알립니다.</p><p class='hint'>결합 중에는 자체 창을 숨긴 상태로 유지하고 제어 막대를 창 밖에 둡니다(창이 화면을 가득 채우면 캡처 순간에만 잠시 숨깁니다). 고정된 떠다니는 요소나 애니메이션이 있으면 정렬되지 않을 수 있습니다.</p>"),
    ),
    "fr": (
        ("1. Démarrage et barre flottante", "<p>Au démarrage, une fine <b>barre flottante</b> apparaît en bas au centre de l'écran, avec une icône dans la zone de notification. De gauche à droite : le logo orange, les trois modes (Zone / Fenêtre / Plein écran, le mode actif sur fond foncé avec un point orange), Capture défilante, Épingler, le raccourci courant et &hellip;. <b>Fermer la barre la réduit seulement dans la zone de notification</b> ; pour quitter, utilisez &hellip; &rarr; Aide &rarr; À propos et quitter ou le menu de l'icône. Faites glisser une zone vide de la barre pour la déplacer ; clic droit sur l'icône pour la rappeler.</p><p>Le bouton &hellip; ouvre un <b>panneau de commandes à deux colonnes</b> (Capture / Édition et sortie à gauche, Paramètres / Aide à droite, 15 lignes). Chaque ligne affiche une icône, un titre avec sa description et la valeur ou le raccourci courant &mdash; <b>lissage, mode par défaut, langue et raccourcis se changent directement dans le panneau</b> et s'appliquent aussitôt.</p>"),
        ("2. Trois modes de capture", "<table><tr><th>Mode</th><th>Utilisation</th><th>Idéal pour</th></tr><tr><td>Zone</td><td>Glisser un rectangle, puis le déplacer ou ajuster les huit poignées</td><td>Une partie de l'écran (défaut)</td></tr><tr><td>Fenêtre</td><td>Survoler une fenêtre pour la surligner et cliquer ; clic droit ou Échap annule</td><td>Une fenêtre entière sans bordure d'ombre transparente</td></tr><tr><td>Plein écran</td><td>L'écran virtuel entier est sélectionné automatiquement</td><td>Le bureau ou plusieurs moniteurs</td></tr></table><p class=\"hint\">L'application masque toutes ses fenêtres avant la capture pour ne jamais apparaître dans l'image. <b>Une barre de confirmation flotte juste à l'extérieur de la sélection</b> : Copier, Reconnaître le texte, Épingler, &#10005; et le bouton foncé <b>OK</b> qui ouvre l'éditeur ; la barre en haut du voile change de mode sur place.</p>"),
        ("3. Raccourci global", "<p>Par défaut <b>Ctrl + Shift + A</b>. Le mode utilisé est le Mode par défaut du panneau de commandes (mémorisé ; le mode actif est sur fond foncé avec un point orange). Modifiez-le dans Paramètres &rarr; Raccourci en appuyant directement sur la combinaison ou en choisissant des modificateurs et une touche principale. Au moins une touche Ctrl / Alt / Maj / Win est requise. Un échec d'enregistrement signifie que la combinaison est occupée. Enregistré dans <code>%APPDATA%\\SnapTool\\settings.json</code>.</p>"),
        ("4. Modifier une capture", "<table><tr><th>Action</th><th>Détails</th></tr><tr><td>Annoter</td><td>Rectangle, ellipse, flèche, ligne, crayon, mosaïque, texte</td></tr><tr><td>Style</td><td>Sélectionnez une forme pour ouvrir le panneau : couleur, épaisseur, style de trait, remplissage, taille de police, gras, fond du texte, flèches aux extrémités</td></tr><tr><td>Transformer</td><td>Rotation 90&deg; (Ctrl+R / Ctrl+Shift+R), miroir horizontal (Ctrl+H) ou vertical (Ctrl+Shift+H) ; image et annotations bougent ensemble, Ctrl+Z annule</td></tr><tr><td>Sortie</td><td>Entrée / Copier, Ctrl+S / Enregistrer, Échap / Annuler ; la capture défilante est une commande distincte (voir section 9)</td></tr></table><p class=\"hint\">Ctrl + molette zoome l'affichage (menu Affichage : Zoom avant / arrière, Taille réelle 1:1, Ajuster à la fenêtre) ; le bouton central fait glisser la vue. L'export garde la résolution d'origine. Une couleur de trait transparente donne des formes sans bordure ; le remplissage dispose d'un curseur d'opacité.</p><p class=\"hint\">La mosaïque n'a pas de style réglable : le panneau de style ne s'ouvre pas lorsque l'outil Mosaïque est actif ou qu'une mosaïque est sélectionnée.</p><p class=\"hint\">Sélectionnez un rectangle ou une ellipse pour afficher quatre <b>poignées d'angle</b> : faites glisser un angle pour modifier largeur, hauteur et forme. Le coin opposé reste fixe, un glissement au-delà retourne la forme et une taille minimale est conservée. Disponible dans le voile et dans la fenêtre d'édition ; les poignées gardent leur taille lors du zoom.</p><p class=\"hint\">Sélectionnez un rectangle, une ellipse ou un texte pour afficher une <b>poignée de rotation</b> au-dessus : glissez pour pivoter librement autour du centre, maintenez Maj pour un pas de 15&deg;, ou réglez l'angle exact avec le curseur Angle de rotation du panneau de style. Édition &rarr; Pivoter la forme sélectionnée tourne par pas de 90&deg; (Ctrl+[ / Ctrl+]). La rotation de l'image entraîne désormais le texte ; l'export garde toujours la résolution d'origine.</p><p class='hint'>Sélectionnez un texte pour donner à son <b>fond</b> les mêmes réglages que le remplissage d’une forme : nuances prédéfinies et curseur <b>Opacité du fond</b> dédié (0&ndash;100 %). Les deux opacités sont mémorisées séparément. Activez <b>Bordure du fond du texte</b> pour entourer le fond arrondi ; choisissez une <b>Couleur de bordure</b> (la nuance ∅ est totalement transparente, donc sans bordure visible), ainsi qu’une épaisseur et un style de trait propres (plein / tirets / points). Fond et bordure se règlent indépendamment et tournent avec le texte.</p><p class='hint'>Le texte reste à la position saisie : le champ de saisie et le texte final partagent la même ligne de base, y compris avec le zoom et sur écran haute densité.</p><p class='hint'>Après la sélection, le bouton <b>Copier</b> tout à gauche de la barre d'outils place l'image d'origine dans le presse-papiers et ferme le voile sans ouvrir l'éditeur. Les captures plein écran et les captures longues sont copiées automatiquement à la fin.</p>"),
        ("5. Extraction de texte (OCR)", "<p>Utilisez Reconnaître le texte dans la barre de confirmation à côté de la sélection, le dock de l'éditeur, ou Édition &rarr; OCR Texte. Chaque ligne reconnue est replacée sur sa position d'origine : sélection, glisser, Ctrl+A / Ctrl+C pour copier, ou les boutons Copier la sélection / Tout copier. Le calque se ferme après copie ; Retour ou Échap ne ferme que le calque. RapidOCR (ONNX) fourni se charge en 1 à 5 s au premier usage puis reste en cache.</p>"),
        ("6. Fichiers et configuration", "<p>Les captures sont enregistrées dans <code>%USERPROFILE%\\Pictures\\Screenshots</code> (chemin affiché dans la ligne Ouvrir le dossier du panneau de commandes, qui l'ouvre ; le menu de l'icône a la même entrée). La configuration est dans <code>%APPDATA%\\SnapTool\\settings.json</code> ; <code>SNAPTOOL_HOME</code> permet de la déplacer pour une version portable.</p>"),
        ("7. Ligne de commande", "<p><code>python snap.py --help</code> liste toutes les options ; <code>--shot</code> capture au démarrage ; <code>--restart</code> nettoie une instance résiduelle et redémarre ; <code>--selftest</code> vérifie le moteur OCR. Disponible aussi dans &hellip; &rarr; Aide &rarr; Ligne de commande.</p>"),
        ("8. Dépannage", "<ul><li><b>Le raccourci ne répond pas :</b> la combinaison est utilisée par une autre application. Modifiez-la ou cliquez sur Zone dans la barre flottante.</li><li><b>« Déjà en cours » sans fenêtre :</b> l'icône est peut-être repliée ; une instance résiduelle peut être remplacée en répondant Oui ou via restart.bat.</li><li><b>Modifications invisibles :</b> l'ancien processus reste actif ; redémarrez avec restart.bat.</li><li><b>Décalage sur écran haute densité :</b> la prise en charge DPI par moniteur est activée ; redémarrez si besoin.</li><li><b>Alerte antivirus :</b> raccourci global et capture d'écran sont souvent signalés à tort ; faites confiance à l'exe non signé.</li></ul>"),
        ("9. Capture défilante", "<p><b>La capture défilante</b> est une commande distincte des trois modes de capture. Lancez-la depuis le bouton Capture défilante de la barre flottante, le panneau de commandes ou le menu de l'icône. Elle <b>n'ouvre pas l'éditeur et ne demande aucun glisser</b> : <b>cliquez sur une fenêtre et le défilement démarre automatiquement</b>.</p><ol><li>Toutes les fenêtres de l'application sont d'abord masquées, puis un voile plein écran apparaît.</li><li>Déplacez la souris : la fenêtre cible est surlignée avec son titre. <b>Un clic gauche la sélectionne</b> ; l'app utilise sa zone client (barre de titre et bordures exclues) comme région de défilement et <b>démarre immédiatement</b> la capture d'images et leur assemblage par corrélation de modèles.</li><li>Pendant le défilement : <b>clic gauche = pause, un autre clic = reprise</b> ; <b>clic droit = fin</b> ; le bouton <b>Terminé ✓</b> de la barre flottante ou Échap termine aussi ; atteindre le bas de page <b>termine automatiquement</b>.</li><li>Une fenêtre d'aperçu s'ouvre à la fin ; enregistrez en PNG / JPG.</li></ol><p class='hint'>Pour éviter les arrêts prématurés, une image quasi identique est revérifiée, les échecs d'alignement sont réessayés avec un pas plus petit, le modèle est pris au milieu de l'image pour ignorer les en-têtes fixes et le curseur est replacé sur la fenêtre avant chaque défilement. La barre affiche le score de correspondance et la notification indique le nombre d'images et le motif d'arrêt.</p><p class='hint'>Les fenêtres de l'app restent masquées pendant l'assemblage et la barre de contrôle est placée hors de la fenêtre (ou brièvement masquée pendant la capture si la fenêtre occupe tout l'écran). Les éléments flottants fixes ou les animations peuvent empêcher l'alignement.</p>"),
    ),
    "de": (
        ("1. Start und schwebende Leiste", "<p>Beim Start erscheint unten in der Bildschirmmitte eine schmale <b>schwebende Leiste</b>, dazu ein Symbol im Infobereich. Von links: oranges Logo, die drei Modus-Schaltflächen (Bereich / Fenster / Vollbild, der aktive dunkel mit orangem Punkt), Scroll-Aufnahme, Anheften, das aktuelle Tastenkürzel und &hellip;. <b>Das Schließen der Leiste minimiert nur in den Infobereich</b>; zum Beenden &hellip; &rarr; Hilfe &rarr; Info und Beenden oder das Tray-Menü nutzen. Eine leere Stelle der Leiste ziehen verschiebt sie; Rechtsklick auf das Symbol holt sie zurück.</p><p>&hellip; öffnet ein <b>zweispaltiges Befehlsfenster</b> (links Aufnahme / Bearbeiten und Ausgeben, rechts Einstellungen / Hilfe, 15 Zeilen). Jede Zeile zeigt Symbol, Titel mit Beschreibung und rechts den aktuellen Wert oder das Kürzel &mdash; <b>Glättung, Standardmodus, Sprache und Tastenkürzel lassen sich direkt im Fenster umschalten</b> und gelten sofort.</p>"),
        ("2. Drei Aufnahmemodi", "<table><tr><th>Modus</th><th>Bedienung</th><th>Geeignet für</th></tr><tr><td>Bereich</td><td>Rechteck ziehen, danach verschieben oder über acht Griffe anpassen</td><td>Einen Teil des Bildschirms (Standard)</td></tr><tr><td>Fenster</td><td>Fenster unter dem Zeiger hervorheben und klicken; Rechtsklick oder Esc bricht ab</td><td>Ein ganzes Fenster ohne transparenten Schattenrand</td></tr><tr><td>Vollbild</td><td>Der gesamte virtuelle Bildschirm wird automatisch gewählt</td><td>Desktop oder mehrere Monitore</td></tr></table><p class=\"hint\">Vor der Aufnahme werden alle eigenen Fenster ausgeblendet, damit sie nicht im Bild landen. <b>Direkt außerhalb der Auswahl schwebt eine Bestätigungsleiste</b>: Kopieren, Text erkennen, Anheften, &#10005; und die dunkle <b>OK</b>-Schaltfläche, die den Editor öffnet; die Leiste oben im Overlay wechselt den Modus direkt.</p>"),
        ("3. Globales Tastenkürzel", "<p>Standard <b>Strg + Umschalt + A</b>. Der verwendete Modus ist der Standardmodus im Befehlsfenster (wird gespeichert; der aktive Modus ist dunkel mit orangem Punkt). Ändern unter Einstellungen &rarr; Tastenkürzel: Kombination direkt drücken oder Modifikatoren plus Haupttaste wählen. Mindestens eine Taste Strg / Alt / Umschalt / Win ist nötig. Schlägt die Registrierung fehl, ist die Kombination belegt. Gespeichert in <code>%APPDATA%\\SnapTool\\settings.json</code>.</p>"),
        ("4. Aufnahme bearbeiten", "<table><tr><th>Aktion</th><th>Details</th></tr><tr><td>Markieren</td><td>Rechteck, Ellipse, Pfeil, Linie, Stift, Mosaik, Text</td></tr><tr><td>Stil</td><td>Form auswählen öffnet das Stilpanel: Farbe, Breite, Linienstil, Füllung, Schriftgröße, Fett, Texthintergrund, Pfeile an Endpunkten</td></tr><tr><td>Transformieren</td><td>90&deg; drehen (Strg+R / Strg+Umschalt+R), horizontal (Strg+H) oder vertikal (Strg+Umschalt+H) spiegeln; Bild und Markierungen wandern gemeinsam, Strg+Z macht es rückgängig</td></tr><tr><td>Ausgabe</td><td>Enter / Kopieren, Strg+S / Speichern, Esc / Abbrechen; Scroll-Aufnahme ist ein eigener Befehl (siehe Abschnitt 9)</td></tr></table><p class=\"hint\">Strg + Mausrad zoomt die Ansicht (Menü Ansicht: Vergrößern, Verkleinern, Originalgröße 1:1, An Fenster anpassen); mit der mittleren Maustaste verschieben. Der Export behält die volle Auflösung. Eine transparente Linienfarbe erzeugt randlose Formen; die Füllung hat einen Deckkraft-Regler.</p><p class=\"hint\">Mosaik hat keine einstellbaren Stile: Das Stilpanel öffnet sich nicht, solange das Mosaik-Werkzeug aktiv oder ein Mosaik ausgewählt ist.</p><p class=\"hint\">Wählen Sie ein Rechteck oder eine Ellipse, um vier <b>Eckgriffe</b> einzublenden: Ziehen Sie eine Ecke, um Breite, Höhe und Form zu ändern. Die gegenüberliegende Ecke bleibt fix, beim Darüberhinausziehen wird die Form gespiegelt und eine Mindestgröße bleibt erhalten. Funktioniert im Overlay und im Editorfenster; beim Zoom behalten die Griffe ihre Größe.</p><p class=\"hint\">Wählen Sie ein Rechteck, eine Ellipse oder einen Text, um darüber einen <b>Drehgriff</b> einzublenden: Ziehen dreht frei um den Mittelpunkt, mit Umschalt rastet es in 15&deg;-Schritten ein, und im Stilpanel lässt sich der Drehwinkel genau einstellen. Bearbeiten &rarr; Ausgewählte Form drehen dreht in 90&deg;-Schritten (Strg+[ / Strg+]). Beim Drehen des gesamten Bildes dreht der Text jetzt mit; Exporte behalten immer die volle Auflösung.</p><p class='hint'>Wählen Sie einen Text, um seinem <b>Hintergrund</b> dieselben Regler wie einer Formfüllung zu geben: vorgegebene Farben und einen eigenen Regler <b>Hintergrund-Deckkraft</b> (0&ndash;100 %). Beide Deckkräfte werden getrennt gespeichert. Mit <b>Rahmen des Texthintergrunds</b> erhält der abgerundete Hintergrund eine Umrandung; wählen Sie eine <b>Rahmenfarbe</b> (das ∅-Feld ist vollständig transparent, also kein sichtbarer Rahmen) sowie eigene Stärke und Linienart (durchgezogen / gestrichelt / gepunktet). Hintergrund und Rahmen lassen sich getrennt ein- und ausschalten und drehen mit dem Text mit.</p><p class='hint'>Der Text bleibt an der eingegebenen Position: Eingabefeld und endgültiger Text teilen dieselbe Grundlinie, auch bei Zoom und auf High-DPI-Bildschirmen.</p><p class='hint'>Nach der Auswahl legt die Schaltfläche <b>Kopieren</b> ganz links in der Symbolleiste das Originalbild in die Zwischenablage und schließt die Maske, ohne den Editor zu öffnen. Vollbild- und Langbild-Aufnahmen werden nach Abschluss automatisch kopiert.</p>"),
        ("5. Texterkennung (OCR)", "<p>Text erkennen in der Bestätigungsleiste neben der Auswahl, im Dock des Editors oder über Bearbeiten &rarr; OCR Text nutzen. Jede erkannte Zeile liegt wieder an ihrer Originalposition: markieren, ziehen, Strg+A / Strg+C zum Kopieren oder Auswahl kopieren / Alles kopieren in der oberen Leiste. Nach dem Kopieren schließt sich die Ebene automatisch; Zurück oder Esc schließt nur die Ebene. Das mitgelieferte RapidOCR (ONNX) lädt beim ersten Mal 1-5 s und bleibt danach im Cache.</p>"),
        ("6. Dateien und Einstellungen", "<p>Aufnahmen landen in <code>%USERPROFILE%\\Pictures\\Screenshots</code> (Pfad in der Zeile Speicherordner öffnen des Befehlsfensters, die ihn gleich öffnet; das Tray-Menü hat denselben Eintrag). Einstellungen in <code>%APPDATA%\\SnapTool\\settings.json</code>; mit <code>SNAPTOOL_HOME</code> lässt sich das Verzeichnis für portable Nutzung verschieben.</p>"),
        ("7. Befehlszeile", "<p><code>python snap.py --help</code> zeigt alle Optionen; <code>--shot</code> nimmt direkt beim Start auf; <code>--restart</code> räumt eine verwaiste Instanz auf und startet neu; <code>--selftest</code> prüft das OCR-Backend. Auch unter &hellip; &rarr; Hilfe &rarr; Befehlszeile.</p>"),
        ("8. Fehlerbehebung", "<ul><li><b>Tastenkürzel reagiert nicht:</b> die Kombination ist belegt. Im Dialog ändern oder die Schaltfläche Bereich in der schwebenden Leiste nutzen.</li><li><b>„Läuft bereits“ ohne Fenster:</b> Symbol im ausgeblendeten Infobereich prüfen; eine verwaiste Instanz lässt sich per Ja im Dialog oder restart.bat ersetzen.</li><li><b>Änderungen fehlen:</b> der alte Tray-Prozess läuft noch; mit restart.bat neu starten.</li><li><b>Koordinaten verschoben:</b> DPI-Erkennung pro Monitor ist aktiv; ggf. neu starten.</li><li><b>Virenwarnung:</b> globale Tastenkürzel plus Bildschirmaufnahme werden oft fälschlich gemeldet; der unsignierten exe vertrauen.</li></ul>"),
        ("9. Scroll-Aufnahme", "<p><b>Scroll-Aufnahme</b> ist ein eigener Befehl neben den drei Aufnahmemodi. Start über die Schaltfläche Scroll-Aufnahme in der schwebenden Leiste, das Befehlsfenster oder das Tray-Menü. Sie <b>öffnet keinen Editor und erfordert kein Ziehen</b>: <b>Fenster anklicken, schon beginnt das automatische Scrollen nach unten</b>.</p><ol><li>Zuerst werden alle eigenen Fenster ausgeblendet, dann erscheint die Vollbild-Überlagerung.</li><li>Beim Bewegen der Maus wird das Zielfenster mit Titel hervorgehoben. <b>Linksklick wählt es aus</b>; die App nutzt seinen Client-Bereich (ohne Titelleiste und Rahmen) als Scroll-Region und <b>beginnt sofort</b> mit dem Aufnehmen und Zusammenfügen per Vorlagenabgleich.</li><li>Während des Scrollens: <b>Linksklick pausiert, weiterer Klick setzt fort</b>; <b>Rechtsklick beendet</b>; <b>Fertig ✓</b> in der schwebenden Leiste oder Esc beendet ebenfalls; am Seitenende <b>endet die Aufnahme automatisch</b>.</li><li>Zum Schluss öffnet sich ein Vorschaufenster; Speichern als PNG / JPG.</li></ol><p class='hint'>Um vorzeitige Abbrüche zu vermeiden, wird eine einzelne unveränderte Aufnahme erneut geprüft, fehlgeschlagene Ausrichtung mit kleinerem Schritt wiederholt, die Vorlage aus der Bildmitte genommen (feste Kopfzeilen werden ignoriert) und der Cursor vor jedem Scrollen auf das Fenster gesetzt. Die Leiste zeigt den Trefferwert, die Benachrichtigung nennt Bilderzahl und Endgrund.</p><p class='hint'>Eigene Fenster bleiben während des Zusammenfügens verborgen, die Steuerleiste liegt außerhalb des Fensters (oder wird beim Aufnehmen kurz ausgeblendet, wenn das Fenster den ganzen Bildschirm füllt). Feste schwebende Elemente oder Animationen können die Ausrichtung verhindern.</p>"),
    ),
    "es": (
        ("1. Inicio y barra flotante", "<p>Al iniciar aparece una <b>barra flotante</b> fina en la parte inferior central de la pantalla, junto con un icono en la bandeja. De izquierda a derecha: el logotipo naranja, los tres modos (Área / Ventana / Pantalla completa, el activo en fondo oscuro con un punto naranja), Captura larga, Fijar, el atajo actual y &hellip;. <b>Cerrar la barra solo la minimiza a la bandeja</b>; para salir use &hellip; &rarr; Ayuda &rarr; Acerca de y salir o el menú de la bandeja. Arrastre una zona vacía de la barra para moverla; clic derecho en el icono para recuperarla.</p><p>El botón &hellip; abre un <b>panel de comandos de dos columnas</b> (Captura / Edición y salida a la izquierda, Ajustes / Ayuda a la derecha, 15 filas). Cada fila muestra un icono, un título con su descripción y el valor o atajo actual &mdash; <b>suavizado, modo predeterminado, idioma y atajos se cambian dentro del panel</b> y se aplican al instante.</p>"),
        ("2. Tres modos de captura", "<table><tr><th>Modo</th><th>Cómo se usa</th><th>Ideal para</th></tr><tr><td>Área</td><td>Arrastre un rectángulo y ajuste con los ocho tiradores</td><td>Una parte de la pantalla (predeterminado)</td></tr><tr><td>Ventana</td><td>Sitúe el cursor sobre una ventana para resaltarla y haga clic; clic derecho o Esc cancela</td><td>Una ventana completa sin el borde de sombra transparente</td></tr><tr><td>Pantalla completa</td><td>Se selecciona automáticamente toda la pantalla virtual</td><td>Escritorio o varios monitores</td></tr></table><p class=\"hint\">La app oculta todas sus ventanas antes de capturar para no aparecer en la imagen. <b>Una barra de confirmación flota justo fuera de la selección</b>: Copiar, Reconocer texto, Fijar, &#10005; y el botón oscuro <b>Aceptar</b> que abre el editor; la barra superior del modo cambia de modo en el sitio.</p>"),
        ("3. Atajo global", "<p>Predeterminado <b>Ctrl + Mayús + A</b>. El modo usado es el Modo predeterminado del panel de comandos (se recuerda; el modo activo se muestra en fondo oscuro con un punto naranja). Cámbielo en Ajustes &rarr; Atajo de teclado pulsando la combinación o eligiendo modificadores y tecla principal. Se requiere al menos una de Ctrl / Alt / Mayús / Win. Si falla el registro, la combinación está ocupada. Se guarda en <code>%APPDATA%\\SnapTool\\settings.json</code>.</p>"),
        ("4. Editar una captura", "<table><tr><th>Acción</th><th>Detalles</th></tr><tr><td>Anotar</td><td>Rectángulo, elipse, flecha, línea, lápiz, mosaico, texto</td></tr><tr><td>Estilo</td><td>Seleccione una forma para abrir el panel: color, grosor, estilo de línea, relleno, tamaño de fuente, negrita, fondo del texto, flechas en los extremos</td></tr><tr><td>Transformar</td><td>Girar 90&deg; (Ctrl+R / Ctrl+Mayús+R), espejo horizontal (Ctrl+H) o vertical (Ctrl+Mayús+H); imagen y anotaciones se mueven juntas, Ctrl+Z deshace</td></tr><tr><td>Salida</td><td>Enter / Copiar, Ctrl+S / Guardar, Esc / Cancelar; la captura larga es un comando independiente (véase la sección 9)</td></tr></table><p class=\"hint\">Ctrl + rueda amplía la vista (menú Ver: Acercar, Alejar, Tamaño real 1:1, Ajustar a la ventana); arrastrar con el botón central desplaza la vista. La exportación conserva la resolución original. Un color de línea transparente crea formas sin borde y el relleno tiene un control de opacidad.</p><p class=\"hint\">Mosaico no tiene estilos ajustables: el panel de estilo no se abre mientras la herramienta Mosaico está activa o hay un mosaico seleccionado.</p><p class=\"hint\">Seleccione un rectángulo o una elipse para mostrar cuatro <b>tiradores de esquina</b>: arrastre cualquier esquina para cambiar ancho, alto y forma. La esquina opuesta queda fija, al arrastrar más allá se invierte la forma y se mantiene un tamaño mínimo. Funciona en la superposición y en la ventana del editor; los tiradores no cambian de tamaño al ampliar la vista.</p><p class=\"hint\">Seleccione un rectángulo, una elipse o un texto para mostrar un <b>tirador de rotación</b> encima: arrastre para girar libremente alrededor del centro, mantenga Mayús para ajustar en pasos de 15&deg; o fije el ángulo exacto con el control Ángulo de rotación del panel de estilo. Editar &rarr; Rotar forma seleccionada gira en pasos de 90&deg; (Ctrl+[ / Ctrl+]). Al girar toda la imagen, el texto gira con ella; la exportación conserva siempre la resolución original.</p><p class='hint'>Seleccione un texto para dar a su <b>fondo</b> los mismos controles que al relleno de una forma: colores predefinidos y un control <b>Opacidad del fondo</b> propio (0&ndash;100 %). Ambas opacidades se guardan por separado. Active <b>Borde del fondo del texto</b> para perfilar el fondo redondeado; elija un <b>Color del borde</b> (la muestra ∅ es totalmente transparente, es decir, sin borde visible) y su propio grosor y estilo de línea (sólida / discontinua / punteada). Fondo y borde se activan por separado y giran junto con el texto.</p><p class='hint'>El texto permanece en la posición escrita: el cuadro de entrada y el texto final comparten la misma línea base, también con zoom y en pantallas de alta densidad.</p><p class='hint'>Tras seleccionar un área, el botón <b>Copiar</b> a la izquierda de la barra de herramientas pone la imagen original en el portapapeles y cierra la máscara sin abrir el editor. Las capturas de pantalla completa y largas se copian automáticamente al terminar.</p>"),
        ("5. Extracción de texto (OCR)", "<p>Use Reconocer texto en la barra de confirmación junto a la selección, el dock del editor o Editar &rarr; OCR Texto. Cada línea reconocida vuelve a su posición original: seleccione, arrastre, Ctrl+A / Ctrl+C para copiar o use Copiar selección / Copiar todo en la barra superior. La capa se cierra sola tras copiar; Volver o Esc cierra solo la capa. RapidOCR (ONNX) incluido tarda 1-5 s la primera vez y luego queda en caché.</p>"),
        ("6. Archivos y configuración", "<p>Las capturas se guardan en <code>%USERPROFILE%\\Pictures\\Screenshots</code> (la ruta aparece en la fila Abrir carpeta del panel de comandos, que la abre; el menú de la bandeja tiene el mismo elemento). La configuración está en <code>%APPDATA%\\SnapTool\\settings.json</code>; <code>SNAPTOOL_HOME</code> permite moverla para uso portátil.</p>"),
        ("7. Línea de comandos", "<p><code>python snap.py --help</code> muestra todas las opciones; <code>--shot</code> captura al iniciar; <code>--restart</code> limpia una instancia residual y reinicia; <code>--selftest</code> verifica el motor OCR. También en &hellip; &rarr; Ayuda &rarr; Línea de comandos.</p>"),
        ("8. Solución de problemas", "<ul><li><b>El atajo no responde:</b> otra app usa la combinación. Cámbiela o pulse Área en la barra flotante.</li><li><b>«Ya en ejecución» sin ventana:</b> el icono puede estar en el área oculta; una instancia residual se sustituye respondiendo Sí o con restart.bat.</li><li><b>No aparecen los cambios:</b> el proceso antiguo sigue residente; reinicie con restart.bat.</li><li><b>Coordenadas desplazadas:</b> la detección DPI por monitor está activa; reinicie si persiste.</li><li><b>Alerta de antivirus:</b> atajos globales y captura de pantalla suelen generar falsos positivos; confíe en el exe sin firma.</li></ul>"),
        ("9. Captura larga", "<p><b>Captura larga</b> es un comando independiente de los tres modos de captura. Se inicia desde el botón Captura larga de la barra flotante, el panel de comandos o el menú de la bandeja. <b>No abre el editor ni requiere arrastrar</b>: <b>haga clic en una ventana y el desplazamiento comienza automáticamente</b>.</p><ol><li>Primero se ocultan todas las ventanas de la app y aparece una superposición a pantalla completa.</li><li>Al mover el ratón, la ventana objetivo se resalta con su título. <b>Un clic izquierdo la selecciona</b>; la app usa su área cliente (sin barra de título ni bordes) como región de desplazamiento y <b>empieza de inmediato</b> a capturar fotogramas y unirlos por coincidencia de plantillas.</li><li>Durante el desplazamiento: <b>clic izquierdo pausa, otro clic continúa</b>; <b>clic derecho termina</b>; el botón <b>Listo ✓</b> de la barra flotante o Esc también terminan; al llegar al final <b>termina automáticamente</b>.</li><li>Al terminar se abre una vista previa; guarde como PNG / JPG.</li></ol><p class='hint'>Para evitar cortes prematuros, un fotograma casi idéntico se vuelve a comprobar, los fallos de alineación se reintentan con un paso menor, la plantilla se toma del centro para omitir cabeceras fijas y el cursor vuelve a la ventana antes de cada giro. La barra muestra la puntuación y la notificación indica los fotogramas y el motivo de fin.</p><p class='hint'>Las ventanas propias siguen ocultas durante la unión y la barra de control se sitúa fuera de la ventana (o se oculta solo al capturar si la ventana ocupa toda la pantalla). Los elementos flotantes fijos o las animaciones pueden impedir la alineación.</p>"),
    ),
    "zh_TW": (
        ("1. 啟動與懸浮條", "<p>啟動後螢幕<b>底部中央會浮出一條迷你懸浮條</b>，系統匣也會出現圖示。由左至右是橘色相機圖示、三個模式按鈕（框選 / 視窗 / 全螢幕，目前模式為深色底加橘點）、「捲動長截圖」與「貼圖」，右側是目前熱鍵提示與「⋯」。<b>關閉懸浮條只會收回系統匣，程式不會結束</b>；要結束請用「⋯ → 說明 → 關於與結束」或系統匣右鍵選單。按住懸浮條空白處可拖到任意位置，系統匣右鍵「顯示主視窗」可叫回，左鍵圖示直接截圖。</p><p>點「⋯」會彈出<b>雙欄命令面板</b>：左欄「截圖 / 編輯與輸出」、右欄「設定 / 說明」，共 15 列。每列左側圖示、中間標題與說明、右側目前取值或快速鍵——<b>平滑度、預設模式、介面語言、熱鍵都能在面板裡就地切換</b>，點一下換下一個值，改完立即生效並自動記住。</p>"),
        ("2. 三種截圖模式", "<table><tr><th>模式</th><th>操作方式</th><th>適用情境</th></tr><tr><td>框選截圖</td><td>拖曳矩形，之後可移動選區或用八個控制點微調</td><td>截取局部內容（預設）</td></tr><tr><td>視窗截圖</td><td>移動滑鼠讓目標視窗高亮後點擊；右鍵或 Esc 取消</td><td>完整截取視窗（自動去掉透明陰影邊框）</td></tr><tr><td>全螢幕截圖</td><td>自動選取整個虛擬螢幕</td><td>整個桌面或多顯示器</td></tr></table><p class=\"hint\">截圖前程式會隱藏自己的所有視窗，不會被拍進圖裡。<b>選區外側會浮出確認條</b>：複製 / 文字抽出 / 釘在桌面 / &#10005; / 深色的<b>確定</b>（開啟編輯器）；遮罩頂端的模式條可就地切換三種模式。</p>"),
        ("3. 全域熱鍵", "<p>預設 <b>Ctrl + Shift + A</b>，使用的模式由命令面板的「預設模式」決定（會記住，目前模式以深色底加橘點標示）。在「⋯ → 設定 → 設定熱鍵…」可直接按鍵錄製，或勾選修飾鍵加選主鍵；至少需要 Ctrl / Alt / Shift / Win 其中一個。若無法註冊，表示組合已被佔用。設定存於 <code>%APPDATA%\\SnapTool\\settings.json</code>。</p>"),
        ("4. 截圖後的編輯", "<table><tr><th>操作</th><th>說明</th></tr><tr><td>標註</td><td>矩形、橢圓、箭頭、直線、畫筆、馬賽克、文字</td></tr><tr><td>樣式</td><td>點選標註後開啟樣式面板，可改顏色、線寬、線型、填色、字級、粗體、文字背景、端點箭頭</td></tr><tr><td>變換</td><td>旋轉 90&deg;（Ctrl+R / Ctrl+Shift+R）、左右鏡像（Ctrl+H）、上下鏡像（Ctrl+Shift+H）；底圖與標註一起變，Ctrl+Z 可復原</td></tr><tr><td>輸出</td><td>Enter / 複製、Ctrl+S / 儲存、Esc / 取消；捲動長截圖是獨立命令（見第 9 節）</td></tr></table><p class=\"hint\">Ctrl + 滾輪可放縮檢視（檢視選單：放大、縮小、實際大小 1:1、配合視窗）；按住中鍵拖曳可平移畫布。僅改變顯示比例，匯出仍是原圖全解析度。線條顏色可選「透明」畫出無邊框圖形，封閉圖形的填色另有不透明度滑桿。</p><p class=\"hint\">馬賽克沒有可調整的樣式：使用馬賽克工具或選中馬賽克標註時，樣式面板都不會彈出。</p><p class=\"hint\">選取矩形或橢圓後會顯示外接矩形的<b>四角控制點</b>，拖動任一角即可改變寬高與形狀：對角保持固定、拖過對角可翻轉、並有最小尺寸保護。截圖遮罩與程式視窗編輯器都可使用，畫布放縮後控制點大小不變。</p><p class=\"hint\">選取矩形、橢圓或文字後，上方會出現<b>旋轉控制柄</b>，拖動即可繞中心任意旋轉（按住 Shift 吸附 15&deg;，樣式面板的「旋轉角度」可精確設定）。選單「編輯 &rarr; 旋轉選取形狀」提供 90&deg; 步進（Ctrl+[ / Ctrl+]）。整張圖片旋轉時文字也會跟著旋轉；匯出永遠是全解析度。</p><p class='hint'>選取文字後，<b>背景色</b>可套用與圖形填色相同的操作（預設色塊＋專屬的<b>背景透明度</b>滑桿 0~100%），兩者的顏色與透明度各自獨立記憶。勾選<b>文字背景框線</b>可為圓角背景描邊：<b>框線顏色</b>可選預設色或「∅ 透明」（透明即看不到框線），並有專屬的粗細與線型（實線／虛線／點線）。背景與框線可分別開關，且會隨文字一起旋轉。</p><p class='hint'>文字會留在輸入的位置：輸入框與完成後的文字共用同一條基線，在畫面縮放或高 DPI 螢幕上也不會位移。</p><p class='hint'>選取範圍後，工具條最左側的「複製」按鈕會直接把原圖放進剪貼簿並關閉遮罩，<b>不開啟編輯器</b>；全螢幕截圖與滾動長截圖完成時也會自動複製原圖。</p>"),
        ("5. 取字（OCR）", "<p>從選區外側確認條的「文字抽出」、編輯器底部 Dock，或「編輯 → OCR 文字抽出」，辨識結果會逐行蓋回原文位置，可選取、拖選、Ctrl+A / Ctrl+C 複製，或用上方工具列「複製選取」「複製全部」。複製後自動收起；「返回」或 Esc 只收起圖層。內建 RapidOCR（ONNX）首次載入約 1~5 秒，之後常駐快取。</p>"),
        ("6. 檔案與設定", "<p>截圖存到 <code>%USERPROFILE%\\Pictures\\Screenshots</code>（命令面板「開啟儲存目錄」一列右側顯示實際路徑，點一下即開啟；系統匣也有同一項）。設定在 <code>%APPDATA%\\SnapTool\\settings.json</code>，可用 <code>SNAPTOOL_HOME</code> 搬到別處，方便攜帶版。</p>"),
        ("7. 命令列", "<p><code>python snap.py --help</code> 列出全部參數；<code>--shot</code> 啟動後立刻截一次；<code>--restart</code> 清理殘留背景實例並重新啟動；<code>--selftest</code> 驗證 OCR 後端。也可在「⋯ → 說明 → 命令列參數」查看。</p>"),
        ("8. 常見問題", "<ul><li><b>熱鍵沒反應：</b>組合被其他程式佔用，請在設定熱鍵裡更換，或直接點懸浮條上的「框選」按鈕。</li><li><b>提示已在執行卻看不到視窗：</b>圖示可能收在通知區摺疊列；也可能是殘留背景實例，在確認框選「是」或執行 restart.bat 重新啟動。</li><li><b>改了程式沒變化：</b>舊的常駐行程仍在跑，用 restart.bat 重啟。</li><li><b>高解析度螢幕座標不準：</b>已啟用每螢幕 DPI 感知，必要時重啟程式。</li><li><b>防毒誤報：</b>全域熱鍵加螢幕擷取容易被誤判，請信任未簽章的 exe。</li></ul>"),
        ("9. 捲動長截圖", "<p><b>捲動長截圖</b>是與三種截圖模式並列的獨立命令，可從懸浮條的長截圖按鈕、命令面板或系統匣選單啟動，<b>不會進入編輯器，也不需要框選</b>：<b>單擊目標視窗即自動向下捲動</b>。</p><ol><li>先隱藏程式所有視窗，再顯示全螢幕遮罩；</li><li>移動滑鼠，目標視窗會高亮並顯示標題；<b>單擊左鍵選取視窗</b>，程式取它的客戶區（自動排除標題列與邊框）作為捲動區域，<b>立即</b>開始逐幀抓圖並用模板比對拼接；</li><li>捲動中：<b>左鍵單擊暫停，再單擊繼續</b>；<b>右鍵單擊結束</b>；點懸浮控制列的「<b>確定 ✓</b>」或按 Esc 也可結束；捲到頁面底部會<b>自動結束</b>；</li><li>結束後彈出預覽視窗，可另存為 PNG / JPG。</li></ol><p class='hint'>為避免提前中斷，單一影格幾乎沒動時會再確認、對齊失敗會以較小幅度重試、範本取自畫面中央以避開固定頂欄，且每次捲動前將游標移回目標視窗。控制列會顯示匹配分數，結束時托盤會通知幀數與結束原因。</p><p class='hint'>拼接期間自有視窗保持隱藏、控制列也會避開視窗區域（視窗佔滿螢幕時會在抓圖瞬間暫時隱藏）。固定懸浮元素或動畫可能導致無法自動對齊。</p>"),
    ),
}

# 关于窗口：简介 / 功能 / 联系邮箱前缀 / 技术说明
# 简介文案与 snapui.ABOUT_HTML 的简体中文保持一致（简体由 ABOUT_HTML 提供）。
_ABOUT: dict[str, tuple[str, str, str, str]] = {
    "zh_TW": (
        "一個自製功能強大的 Windows 桌面截圖軟體。",
        "功能：三種截圖模式、物件化標註編輯、整圖旋轉 / 鏡像、畫筆端點箭頭、獨立「捲動長截圖」命令、中文 OCR 逐行蓋回取字、全域熱鍵自訂、8 種介面語言。",
        "聯繫信箱：",
        "技術棧：Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime)。第三方元件授權：PySide6 (LGPL)、RapidOCR / PaddleOCR / OpenCV (Apache-2.0)、ONNX Runtime (MIT)。",
    ),
    "en": (
        "A powerful, self-built Windows desktop screenshot tool.",
        "Features: three capture modes, object-based annotations, whole-image rotate / flip, pen endpoint arrows, a dedicated Scrolling Capture command, per-line OCR overlay, custom global hotkey, 8 interface languages.",
        "Contact: ",
        "Built with Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime). Third-party licenses: PySide6 (LGPL), RapidOCR / PaddleOCR / OpenCV (Apache-2.0), ONNX Runtime (MIT).",
    ),
    "ja": (
        "自作の機能が強力な Windows デスクトップ スクリーンショット ソフトです。",
        "機能：3 つのキャプチャ モード、オブジェクトベースの注釈、画像全体の回転 / 反転、ペンの端点矢印、専用の「スクロール キャプチャ」コマンド、行単位の OCR 重ね表示、ショートカットのカスタマイズ、8 言語のインターフェース。",
        "連絡先メール: ",
        "技術: Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime)。第三者ライセンス: PySide6 (LGPL)、RapidOCR / PaddleOCR / OpenCV (Apache-2.0)、ONNX Runtime (MIT)。",
    ),
    "ko": (
        "직접 만든 강력한 Windows 데스크톱 스크린샷 소프트웨어입니다.",
        "기능: 세 가지 캡처 모드, 객체 기반 주석, 이미지 전체 회전 / 반전, 펜 끝점 화살표, 전용 '스크롤 캡처' 명령, 줄 단위 OCR 덮어쓰기, 전역 단축키 사용자 지정, 8가지 인터페이스 언어.",
        "연락처 이메일: ",
        "기술: Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime). 서드파티 라이선스: PySide6 (LGPL), RapidOCR / PaddleOCR / OpenCV (Apache-2.0), ONNX Runtime (MIT).",
    ),
    "fr": (
        "Un logiciel de capture d'écran Windows puissant, fait maison.",
        "Fonctions : trois modes de capture, annotations objets, rotation / miroir de l'image, flèches aux extrémités du crayon, commande dédiée « Capture défilante », OCR ligne par ligne, raccourci global personnalisable, 8 langues d'interface.",
        "Contact : ",
        "Technologies : Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime). Licences tierces : PySide6 (LGPL), RapidOCR / PaddleOCR / OpenCV (Apache-2.0), ONNX Runtime (MIT).",
    ),
    "de": (
        "Eine selbst entwickelte, leistungsstarke Screenshot-Software für Windows.",
        "Funktionen: drei Aufnahmemodi, objektbasierte Markierungen, Rotation / Spiegelung des ganzen Bilds, Pfeile an Stiftenden, eigener Befehl „Scroll-Aufnahme“, zeilenweise OCR-Überlagerung, eigenes globales Tastenkürzel, 8 Oberflächensprachen.",
        "Kontakt: ",
        "Technik: Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime). Drittanbieter-Lizenzen: PySide6 (LGPL), RapidOCR / PaddleOCR / OpenCV (Apache-2.0), ONNX Runtime (MIT).",
    ),
    "es": (
        "Un software de captura de pantalla para Windows potente y hecho por uno mismo.",
        "Funciones: tres modos de captura, anotaciones basadas en objetos, rotación / espejo de toda la imagen, flechas en los extremos del lápiz, comando dedicado « Captura larga », OCR superpuesto por líneas, atajo global personalizable, 8 idiomas de interfaz.",
        "Contacto: ",
        "Tecnología: Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime). Licencias de terceros: PySide6 (LGPL), RapidOCR / PaddleOCR / OpenCV (Apache-2.0), ONNX Runtime (MIT).",
    ),
}

# 命令行说明（纯文本）
_CLI: dict[str, str] = {
    "zh_TW": """截圖助手 —— 命令列參數

  python snap.py              正常啟動：顯示主視窗 + 系統匣常駐
  python snap.py --shot       啟動後立即截一次圖（使用預設模式）
  python snap.py --restart    結束背景殘留實例並重新啟動
  python snap.py --selftest   只跑後端自檢，不進入介面
  python snap.py --help       顯示本說明（也可寫 -h 或 /?）

日常使用請雙擊 run-silent.bat（無黑視窗）。程式是單實例，重複啟動會先喚醒
已有實例並顯示主視窗；若看不到介面，在確認框選「是」即可結束背景實例並重啟，
也可直接雙擊 restart.bat。三種模式：框選、視窗、全螢幕。
預設模式與熱鍵保存在 %APPDATA%\\SnapTool\\settings.json。
更多說明見「說明 → 使用說明」或 README.md。
""",
    "en": """SnapTool - Command line options

  python snap.py              Normal start: main window + tray
  python snap.py --shot       Capture once immediately after startup
  python snap.py --restart    End a stale background instance and restart
  python snap.py --selftest   Run backend self-test only (no UI)
  python snap.py --help       Show this help (also -h or /?)

For daily use double-click run-silent.bat (no console window). The app is
single-instance: a second launch wakes the running instance and shows its main
window; if nothing appears, answer Yes to replace it, or run restart.bat.
Three modes: area, window and full screen. The default mode and hotkey are
stored in %APPDATA%\\SnapTool\\settings.json.
See Help -> User Guide or README.md for details.
""",
    "ja": """スクリーンショット - コマンドライン オプション

  python snap.py              通常起動：メインウィンドウ + トレイ常駐
  python snap.py --shot       起動直後に 1 回キャプチャ
  python snap.py --restart    残存インスタンスを終了して再起動
  python snap.py --selftest   バックエンドの自己診断のみ（UI なし）
  python snap.py --help       このヘルプを表示（-h / /? でも可）

通常は run-silent.bat をダブルクリックしてください（コンソール非表示）。
単一インスタンスなので、二重起動時は実行中のインスタンスを呼び出します。
ウィンドウが見えない場合は確認画面で「はい」を選ぶか restart.bat を実行。
モードは範囲 / ウィンドウ / 全画面の 3 種類。既定モードとショートカットは
%APPDATA%\\SnapTool\\settings.json に保存されます。
詳細は ヘルプ → 使い方 または README.md を参照してください。
""",
    "ko": """스크린샷 도우미 - 명령줄 옵션

  python snap.py              일반 시작: 주 창 + 트레이 상주
  python snap.py --shot       시작 직후 한 번 캡처
  python snap.py --restart    잔여 백그라운드 인스턴스 종료 후 재시작
  python snap.py --selftest   백엔드 자체 검사만 실행(UI 없음)
  python snap.py --help       이 도움말 표시(-h 또는 /? 가능)

일상적으로는 run-silent.bat을 실행하세요(콘솔 창 없음). 단일 인스턴스이므로
다시 실행하면 기존 인스턴스를 깨웁니다. 창이 보이지 않으면 확인 창에서 '예'를
선택하거나 restart.bat을 실행하세요. 모드는 영역 / 창 / 전체 화면 세 가지이며
기본 모드와 단축키는 %APPDATA%\\SnapTool\\settings.json에 저장됩니다.
자세한 내용은 도움말 → 사용 설명서 또는 README.md를 참고하세요.
""",
    "fr": """Capture d'écran - Options de ligne de commande

  python snap.py              Démarrage normal : fenêtre principale + barre
  python snap.py --shot       Capture immédiate au démarrage
  python snap.py --restart    Terminer l'instance résiduelle et redémarrer
  python snap.py --selftest   Auto-test du backend uniquement (sans interface)
  python snap.py --help       Afficher cette aide (-h ou /? également)

Au quotidien, double-cliquez sur run-silent.bat (sans console). L'application
est à instance unique : un second lancement réveille l'instance en cours.
Si aucune fenêtre n'apparaît, répondez Oui ou lancez restart.bat.
Trois modes : zone, fenêtre, plein écran. Le mode et le raccourci par défaut
sont enregistrés dans %APPDATA%\\SnapTool\\settings.json.
Voir Aide -> Guide ou README.md pour plus de détails.
""",
    "de": """Bildschirmfoto - Befehlszeilenoptionen

  python snap.py              Normaler Start: Hauptfenster + Infobereich
  python snap.py --shot       Direkt nach dem Start einmal aufnehmen
  python snap.py --restart    Verwaiste Instanz beenden und neu starten
  python snap.py --selftest   Nur Backend-Selbsttest (ohne Oberfläche)
  python snap.py --help       Diese Hilfe anzeigen (auch -h oder /?)

Für den Alltag run-silent.bat doppelklicken (ohne Konsole). Die App ist eine
Einzelinstanz: ein zweiter Start weckt die laufende Instanz. Falls kein Fenster
erscheint, mit Ja bestätigen oder restart.bat ausführen.
Drei Modi: Bereich, Fenster, Vollbild. Standardmodus und Tastenkürzel liegen in
%APPDATA%\\SnapTool\\settings.json.
Mehr in Hilfe -> Handbuch oder README.md.
""",
    "es": """Captura de pantalla - Opciones de línea de comandos

  python snap.py              Inicio normal: ventana principal + bandeja
  python snap.py --shot       Capturar una vez al iniciar
  python snap.py --restart    Cerrar la instancia residual y reiniciar
  python snap.py --selftest   Solo autoprueba del backend (sin interfaz)
  python snap.py --help       Mostrar esta ayuda (también -h o /?)

Para uso diario, haga doble clic en run-silent.bat (sin consola). La app es de
instancia única: un segundo inicio despierta la instancia activa. Si no aparece
ninguna ventana, responda Sí o ejecute restart.bat.
Tres modos: área, ventana y pantalla completa. El modo y el atajo predeterminados
se guardan en %APPDATA%\\SnapTool\\settings.json.
Vea Ayuda -> Guía o README.md para más detalles.
""",
}


def help_html(lang: str | None = None) -> str:
    code = lang or LANG.current
    if code == "zh_CN":
        from snapui import HELP_HTML  # 延迟导入，避免与 snapui 形成循环
        return HELP_HTML
    sections = _HELP.get(code) or _HELP["en"]
    body = "".join(f"<h2>{title}</h2>{text}" for title, text in sections)
    # v34 贴图钉在桌面：新增章节用 i18n 文案统一渲染，避免维护多份长 HTML
    body += (
        f"<h2>10. {t('钉在桌面')}</h2>"
        f"<p>{t('贴图用法')}</p>"
        f"<p class='hint'>{t('贴图操作')}</p>"
    )
    return f"<html><head>{_CSS}</head><body>{body}</body></html>"


def about_html(lang: str | None = None, email: str = "283096251@qq.com",
               name: str | None = None) -> str:
    code = lang or LANG.current
    if code == "zh_CN":
        from snapui import ABOUT_HTML
        return ABOUT_HTML
    desc, features, contact, tech = _ABOUT.get(code) or _ABOUT["en"]
    title = name or ""
    return f"""
<div style="font-family:'Microsoft YaHei',sans-serif; font-size:13px; color:#1f2937; line-height:1.6;">
<p style="font-size:19px; font-weight:bold; margin:0 0 8px 0;">{title}</p>
<p>{desc}</p>
<p>{features}</p>
<p style="font-size:13px;">{contact}<a href="mailto:{email}" style="color:#0a6ed1;">{email}</a></p>
<p style="font-size:12px; color:#6b7280;">{tech}</p>
</div>
"""


def cli_help(lang: str | None = None, name: str | None = None) -> str:
    code = lang or LANG.current
    if code == "zh_CN":
        from snapui import CLI_HELP
        return CLI_HELP
    text = _CLI.get(code) or _CLI["en"]
    if name:
        # 第一行是「<名字> —— 命令行参数」之类，替换成当前语言下的程序名
        lines = text.split("\n")
        if " - " in lines[0] or " —— " in lines[0]:
            sep = " —— " if " —— " in lines[0] else " - "
            lines[0] = name + sep + lines[0].split(sep, 1)[1]
        text = "\n".join(lines)
    return text


def cli_help_html(lang: str | None = None, name: str | None = None) -> str:
    return (
        "<html><body style=\"font-family:'Microsoft YaHei';font-size:13px;\">"
        "<h2>" + escape(t("命令行参数")) + "</h2><pre style=\"font-family:Consolas,"
        "'Microsoft YaHei';font-size:13px;\">"
        + escape(cli_help(lang, name))
        + "</pre></body></html>"
    )


__all__ = ["help_html", "about_html", "cli_help", "cli_help_html"]

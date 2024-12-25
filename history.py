#　V1 LED自体を検出１
#	・LED自体をパターンマッチングで見つけようとした
#	・テンプレートは隣のボタン（予約）を込みで撮影
#	・ドア開閉はテンプレートのズーム率で判定
#	・４Hの暗さで見つけられずエラー多発＆遅い
#	・１判定＝1分程度（論外）
#
# V2 LED自体を検出２
#	・ズーム率を変えて探すのは時間がかかりすぎる反省
#	・OPENとCLOSEの２パターンをマッチングさせ、近い方を採用する
#	・タイマ（３パターン）×開閉（２パターン）＝６回マッチング
#	・１判定＝40秒程度
#
# V3 カステリを検出
#	・食洗器に貼ったカステリシールを目印に探す
#	・カステリマークの横にあるLEDの輝度（というか赤ドット）を数える
#	・カステリ（開閉）の２回しかマッチングしない
#	・１秒以内
#
# V4 ３ボタンを検出
#	・カメラ性能が悪すぎて、カステリマークが判別できない（ほぼ単なる丸）
#	・３ボタン並び（電源・モード・予約）を検出して位置を確定し、LEDを数える
#	・１秒以内
#
#	TODO: LEDの赤要素を数えようとしているが、赤外線カメラではもともと無理な気がする
#			輝度を使ってみてはどうか（明るいドット数を数える）


def init_camera():
	global picam

	picam = Picamera2()

	picam.configure(
		picam.create_preview_configuration(
			main={"format": 'XRGB8888', "size": (CAPTURE_WIDTH, CAPTURE_HEIGHT)}))
	picam.start()


def init_washer():
	global temp_dark_close, temp_dark_open
	global temp_light_close, temp_light_open

	temp_light_close = cv2.imread( TEMP_CASTELLI_LIGHT_CLOSE )
	temp_light_close = cv2.cvtColor( temp_light_close, cv2.COLOR_RGB2GRAY )

	temp_light_open  = cv2.imread( TEMP_CASTELLI_LIGHT_OPEN )
	temp_light_open  = cv2.cvtColor( temp_light_open, cv2.COLOR_RGB2GRAY )

	temp_dark_close  = cv2.imread( TEMP_CASTELLI_DARK_CLOSE )
	temp_dark_close  = cv2.cvtColor( temp_dark_close, cv2.COLOR_RGB2GRAY )

	temp_dark_open   = cv2.imread( TEMP_CASTELLI_DARK_OPEN )
	temp_dark_open   = cv2.cvtColor( temp_dark_open, cv2.COLOR_RGB2GRAY )

	init_camera()
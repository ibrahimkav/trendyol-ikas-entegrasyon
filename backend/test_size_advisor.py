import requests, json, sqlite3
B = 'http://localhost:8000'

# 1) Beden tablosunu metin olarak ayristir (kullanicinin tablosunu yapistirarak)
table_text = """S: Bel 71-76, Gogus 83-88, Boy 165-170, Kilo 50-60
M: Bel 76-81, Gogus 88-93, Boy 170-175, Kilo 60-70
L: Bel 81-86, Gogus 93-98, Boy 175-180, Kilo 70-80
XL: Bel 86-91, Gogus 98-103, Boy 180-185, Kilo 80-90
XXL: Bel 91-96, Gogus 103-108, Boy 185-190, Kilo 90-100"""
r = requests.post(B + '/api/size-chart/parse-text', json={'text': table_text})
rows = r.json().get('sizes', [])
print('1) metin ayristirma:', r.status_code, '| beden sayisi:', r.json().get('size_count'), '| bedenler:', [x['size'] for x in rows])

# 2) Kullaniciye ornek gorseliyle tabloyu kaydet
payload = {
  'product_name': 'Ornek Urun (beden tablosu gorseli)',
  'image_url': 'https://cdn.dsmcdn.com/ty1000057/product/media/images/prod/PIM/20260116/13/fd8119c5-fc7d-4ba0-803f-b2c41c1b4cd0/1_org_zoom.jpg',
  'notes': 'Normal kalip, pamuklu kumas.',
  'sizes': rows
}
r = requests.post(B + '/api/size-chart/DEMO123', json=payload)
print('2) tablo kaydi:', r.status_code, r.json().get('message'))

# 3) MUSTERI SORUSU: boyum 180 kilom 80 -> beden onerisi bekleniyor
qa_id = requests.post(B + '/api/customer-qa/', json={'question': 'Boyum 180 kilom 80 hangi beden almayi uygun gorursunuz?'}).json()['qa_id']
s = requests.post(B + '/api/customer-qa/ai-suggest', json={'question': 'Boyum 180 kilom 80 hangi beden almayi uygun gorursunuz?', 'qa_id': qa_id, 'product_code': 'DEMO123'}).json()
print('3) beden onerisi:', s.get('recommended_size'), '| kaynak:', s.get('answer_source'), '| guven:', s.get('confidence'))
print('   CEVAP:', s.get('suggested_answer', '').replace(chr(10), ' | '))

# 4) Bel olcusu ile test
s2 = requests.post(B + '/api/customer-qa/ai-suggest', json={'question': 'Belim 88 cm ve boyum 182, hangi beden uyar?', 'qa_id': qa_id, 'product_code': 'DEMO123'}).json()
print('4) bel+boy onerisi:', s2.get('recommended_size'), '| guven:', s2.get('confidence'))

# 5) Tablosuz urun -> normal ogrenme akisi
s3 = requests.post(B + '/api/customer-qa/ai-suggest', json={'question': 'Boyum 180 kilom 80 hangi beden?', 'qa_id': qa_id}).json()
print('5) tablosuz soru kaynagi:', s3.get('answer_source', 'learned/generic'), '(tablo yoksa normal akis)')

# 6) Temizlik
requests.delete(B + '/api/size-chart/DEMO123')
c = sqlite3.connect(r'trendyol_data.db'); c.execute('DELETE FROM qa_records WHERE qa_id = ?', (qa_id,)); c.commit(); c.close()
print('6) temizlik OK - HEPSI TAMAM')

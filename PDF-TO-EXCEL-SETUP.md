# PDF to Excel Converter — स्थानिक स्थापना व चाचणी

## काय समाविष्ट आहे
- `pdf-to-excel.html`: Digital SATHIDAR मधील स्वतंत्र upload UI, drag & drop, conversion status आणि XLSX download.
- `backend/app.py`: FastAPI service. डिजिटल PDF साठी pdfplumber आणि scanned/image PDF साठी Tesseract OCR + pdf2image वापरतो. OCR साठी कोणतीही Paid API वापरली जात नाही.
- अनेक PDF फाइल्स, अनेक पेजेस आणि अनेक टेबल्स: प्रत्येक शोधलेले टेबल स्वतंत्र Excel worksheet मध्ये ठेवले जाते. Scanned OCR हे अंदाजे row/column reconstruction करते; मूळ टेबलची रचना प्रत्येक स्कॅनमध्ये अचूक मिळेल याची हमी नाही.

## आवश्यक सॉफ्टवेअर
- Python 3.10 किंवा नंतरची आवृत्ती.
- Tesseract OCR.
- Poppler utilities (pdf2image साठी).
- Tesseract language data: English साठी `eng.traineddata`, मराठीसाठी `mar.traineddata`. Tesseract मध्ये `tessdata` folder मध्ये दोन्ही फाइल्स असाव्यात.
- Python dependencies: `backend/requirements.txt`.

### Windows (उदाहरण)
1. Python स्थापित करा.
2. Tesseract OCR स्थापित करा आणि English + Marathi language data निवडा. नंतर terminal मध्ये `tesseract --list-langs` चालवून `eng` व `mar` दिसतात का ते तपासा.
3. Poppler for Windows स्थापित करा आणि त्याच्या `Library/bin` folder ला PATH मध्ये जोडा.
4. Repository root मधून:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   py -m pip install -r backend/requirements.txt
   ```
5. Tesseract PATH मध्ये नसेल तर `backend/.env.example` मधील `TESSERACT_CMD` प्रमाणे environment variable सेट करा.
6. Backend चालवा:
   ```powershell
   uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
   ```
7. `pdf-to-excel.html` ब्राउझरमध्ये उघडा. Backend API URL `http://127.0.0.1:8000` ठेवा. `http://127.0.0.1:8000/api/health` उघडून `marathi_available: true` तपासा.

## चाचणी
```powershell
py -m pip install -r backend/requirements.txt
py -m unittest discover -s backend/tests -v
```
नंतर UI मध्ये खालील तपासा:
1. Digital PDF ज्यामध्ये selectable text व स्पष्ट टेबल आहे — Automatic किंवा Digital mode.
2. Scanned Marathi PDF — OCR mode, भाषा English + Marathi.
3. Multi-page PDF — सर्व पेजमधील टेबल्स स्वतंत्र worksheets मध्ये आहेत का.
4. एकावेळी दोन PDF — दोन्ही फाइल्समधील worksheets आहेत का.
5. Non-PDF, corrupt PDF, oversized PDF आणि OCR language data नसताना योग्य error दिसतो का.

## मर्यादा आणि सुरक्षा
- GitHub Pages static hosting आहे; ते Python backend चालवत नाही. त्यामुळे UI एकट्याने live GitHub Pages वर converter करू शकत नाही. सार्वजनिक production वापरासाठी HTTPS backend deploy करून `pdf-to-excel.html` मधील API URL बदला आणि CORS मध्ये फक्त त्या domain ला परवानगी द्या.
- सध्या API स्थानिक development साठी आहे. Sensitive documents public backend वर पाठवू नका. Production मध्ये authentication, rate limits, request logging policy, antivirus/isolated processing, cleanup, TLS आणि stricter CORS जोडणे आवश्यक आहे.
- OCR output हा machine-recognition परिणाम आहे; शाळा/शासकीय वापरापूर्वी Excel मधील आकडे, मराठी नावे, शीर्षके आणि स्तंभ manually verify करा.
- Digital PDF मध्ये pdfplumber ला table lines/layout न समजल्यास Automatic mode OCR fallback करतो. OCR हे approximate columns तयार करते; जटिल merged cells किंवा तिरपे/धूसर स्कॅनमध्ये manual correction लागू शकते.
- हा बदल `feature/pdf-to-excel` branch मध्ये review साठी आहे; `main` मध्ये merge केलेला नाही.

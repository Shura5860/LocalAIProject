# 🎯 AURA-CORE: Teknik & Mimari Mülakat Hazırlık Rehberi (Question_Ask.md)

Bu doküman; **Senior AI Engineer**, **Systems / Infrastructure Architect** ve **Staff Software Engineer** mülakatlarında, teknik mülakatı yöneten Principal Engineer'lar, Head of Engineering ve teknik İK liderleri tarafından sorulabilecek **derinlemesine, zorlayıcı ve sistemin zayıf/güçlü yönlerini yoklayan** gerçek mülakat sorularını ve bunların arkasındaki mühendislik mantığını içerir.

---

## 📑 İÇİNDEKİLER
1. [Bölüm 1: Mimari & Sistem Tasarımı (High-Level Architecture)](#bölüm-1-mimari--sistem-tasarımı)
2. [Bölüm 2: Vektör Motoru & Rust Çekirdeği (Low-Level Systems)](#bölüm-2-vektör-motoru--rust-çekirdeği)
3. [Bölüm 3: LLM Çıkarımı, Tokenizasyon & Bellek Yönetimi](#bölüm-3-llm-çıkarımı-tokenizasyon--bellek-yönetimi)
4. [Bölüm 4: ReAct Ajan Döngüsü & Araç Güvenliği (Agentic Systems)](#bölüm-4-react-ajan-döngüsü--araç-güvenliği)
5. [Bölüm 5: Ürünleştirme, Lisanslama & Tersine Mühendislik Savunması](#bölüm-5-ürünleştirme-lisanslama--tersine-mühendislik)
6. [Bölüm 6: Davranışsal & Mühendislik Olgunluğu (Behavioral & Trade-offs)](#bölüm-6-davranışsal--mühendislik-olgunluğu)

---

## Bölüm 1: Mimari & Sistem Tasarımı

### S1. "Neden hazır bir bulut API'si (OpenAI, Claude) kullanmak yerine yerel (on-premise) bir mimari kurdun? Bulut API'si kullanmak şirkete çok daha ucuza ve hızlıya gelmez miydi?"
> **İdeal Cevap Yaklaşımı:**
> "Buradaki temel karar maliyetten ziyade **veri mahremiyeti ve yasal regülasyonlar (Compliance)**. 
> Çalıştığımız senaryoda hedef kitle; kaynak kodlarını dışarı çıkaramayan yazılım şirketleri, hasta verisi işleyen sağlık kurumları veya sözleşme analiz eden hukuk bürolarıdır. OpenAI gibi bulut sağlayıcılarına veri göndermek KVKK, GDPR ve kurumsal gizlilik politikalarını ihlal eder. 
> Ayrıca bulut API'lerinde ağ gecikmesi (network latency), rate limitler ve üçüncü taraf bağımlılığı (vendor lock-in) vardır. Yerel mimari; internet bağlantısı tamamen kesilmiş (air-gapped) bir veri merkezinde veya dizüstü bilgisayarda deterministik, sıfır veri sızıntısıyla çalışmayı garanti eder."

### S2. "FastAPI, Tauri, Rust ve C++ çıkarım motoru... 4 farklı teknoloji katmanı var. Bu mimarinin bakım maliyeti (maintenance overhead) ve karmaşıklığı çok yüksek değil mi?"
> **İdeal Cevap Yaklaşımı:**
> "Evet, heterojen bir mimari getirdiği doğru. Ancak bu seçimlerin her biri katı birer mühendislik kısıtından doğdu:
> 1. **Tauri:** Kullanıcıya modern bir masaüstü deneyimi sunarken Electron'un 300MB+ RAM ayak izini reddedip <35MB RAM tüketmek için seçildi. Çünkü yan tarafta 4.5 GB'lık bir LLM çalışacak; belleğin her megabaytı değerlidir.
> 2. **Rust Core:** Vektör matematiğini Python GIL (Global Interpreter Lock) engeline takılmadan SIMD hızında çalıştırmak için seçildi.
> 3. **FastAPI:** Python'un zengin yapay zeka ekosistemini (PyO3, sentence-transformers, llama-cpp) asenkron SSE (Server-Sent Events) ile arayüze bağlayan hafif bir orkestratör görevindedir.
> Her katmanın sınırları (boundaries) net HTTP/IPC protokolleriyle ayrıldığı için monolitik bir spagetti kod oluşmaz; her bileşen bağımsız test edilebilir."

---

## Bölüm 2: Vektör Motoru & Rust Çekirdeği

### S3. "Vektör veri tabanını neden Rust ile sıfırdan yazdın? Qdrant, Chroma veya pgvector kullansaydın ne kaybederdin?"
> **İdeal Cevap Yaklaşımı:**
> "Masaüstü ve tekil istemci (thin-client) dağıtımında kullanıcıdan Docker kurmasını veya arka planda PostgreSQL servisi yönetmesini bekleyemeyiz. Kullanıcı bir `.exe` veya script çalıştırdığında her şeyin süreç içi (in-process) ayağa kalkması gerekir.
> Python'daki Chroma/FAISS kütüphaneleri ise bellek sızıntılarına ve GIL blokajlarına yatkındır. 
> Rust ile PyO3 C-FFI kullanarak vektör motorunu doğrudan Python sürecine gömdük. Sıfır ağ gecikmesi, sıfır serileştirme kaybı elde ettik. Bunun ödünleşimi (trade-off) ise Write-Ahead Logging (WAL) ve veri sıkıştırma (vacuum) algoritmalarını kendimizin yazmak zorunda kalması oldu."

### S4. "Write-Ahead Logging (WAL) mekanizmasını nasıl uyguladın? Elektrik kesilirse veya süreç aniden çökerse veri kaybını nasıl önlüyorsun?"
> **İdeal Cevap Yaklaşımı:**
> "Tüm ekleme (`insert`) ve silme (`delete`) operasyonları, bellekteki HNSW grafiğine işlenmeden önce diske sıralı ve append-only formatta (`wal.log`) yazılır ve `fsync` edilir.
> Sistem yeniden başlatıldığında:
> 1. Eğer kalıcı snapshot dosyası varsa bellek önce snapshot'tan yüklenir.
> 2. Snapshot'tan sonraki tüm WAL kayıtları kronolojik olarak tekrar oynatılır (replay).
> 3. Böylece ani çökme anında bile en son kaydedilen vektörler kurtarılır. WAL dosyası belirli bir boyuta ulaştığında ise arka planda bir 'Vacuum' çalışarak logları temizler ve tek bir optimize snapshot üretir."

### S5. "HNSW grafiğinde silme (delete) işlemi zordur; grafın bağlantılarını koparabilir. Sen silme işlemini nasıl çözdün?"
> **İdeal Cevap Yaklaşımı:**
> "HNSW üzerinde doğrudan düğüm silmek grafın navigasyonel özelliklerini bozar. Bu nedenle endüstri standardı olan **Tombstone (Mezar Taşı)** yaklaşımını kullandık.
> Bir vektör silindiğinde, graf düğümü fiziksel olarak koparılmaz; sadece 'silindi' bayrağı (bitmask) işaretlenir. Arama anında bu düğümler atlanır. Tombstone sayısı toplam indeksin %20'sini aştığında ise arka planda çalışan `vacuum` süreci grafı temiz düğümlerle baştan kurar."

---

## Bölüm 3: LLM Çıkarımı, Tokenizasyon & Bellek Yönetimi

### S6. "Modeli neden uygulamanın başında doğrudan belleğe yüklemiyorsun? 'On-Demand Loading' seçiminin sebebi nedir?"
> **İdeal Cevap Yaklaşımı:**
> "Kullanıcı bu uygulamayı arka planda açık tutup aynı anda oyun oynayabilir, video render alabilir veya IDE çalıştırabilir. 
> Eğer 7B modeli sürekli VRAM'de tutarsak 4.5 GB ekran kartı belleğini kalıcı olarak işgal etmiş oluruz. 'On-Demand / Lazy Loading' stratejisiyle:
> - Kullanıcı soru sormadığı sürece VRAM tüketimi **0 MB**'tır.
> - İlk sorgu geldiğinde model C++ mmap ve AVX2 thread havuzuyla saniyeler içinde belleğe haritalanır.
> - Kullanıcı 3B ile 7B arasında geçiş yaptığında ise eski model bağlamı serbest bırakılır (deallocation) ve yeni model yüklenir. Bu sayede bellek çakışması (OOM) yaşanmaz."

### S7. "Modern BPE Tokenizer'a neden geçtiniz? Rust motorunuzdaki eski SimpleTokenizer'ın eksikliği neydi?"
> **İdeal Cevap Yaklaşımı:**
> "Eski naive tokenizer, kelimeleri sadece boşluklardan ve noktalama işaretlerinden ayıran ilkel bir mantığa sahipti. Qwen 2.5 gibi modeller ise 152.064 kelimelik Byte-Pair Encoding (BPE) kullanır.
> Türkçe gibi eklemeli (agglutinative) dillerde veya kod bloklarındaki özel karakterlerde (girintiler, tablar, unicode semboller), ilkel tokenizer kelime kökünü bulamayınca çöküyor veya modele saçma sapan token indeksleri veriyordu. BPE tokenizer'a geçerek byte-fallback desteği sağladık; böylece Türkçe ekler ve karmaşık Python/Rust sözdizimi sıfır bozulmayla işlenebilir hale geldi."

### S8. "Neden Ollama gibi hazır bir aracı arka planda çalıştırmak yerine `llama-cpp-python` kütüphanesini koda gömdünüz?"
> **İdeal Cevap Yaklaşımı:**
> "Ollama bir son kullanıcı için harika bir araçtır, ancak bağımsız bir yazılım ürünü (COTS product) dağıtıyorsanız üçüncü taraf bir daemon'a bağımlı olmak dağıtım güvenilirliğini düşürür:
> - Ollama sistemde kurulu mu? Hangi sürümü var? Port çakışması var mı? Bunların hepsi destek maliyetidir.
> - Kendi binary'mizin içine gömülü C++ AVX2 motoru kullandığımızda; modelin context boyutunu, GPU katman sayısını (`n_gpu_layers`), thread sayısını ve streaming yanıtını doğrudan Python içerisinden deterministik şekilde yönetebiliyoruz."

---

## Bölüm 4: ReAct Ajan Döngüsü & Araç Güvenliği

### S9. "ReAct (Reasoning + Acting) ajan döngüsünün sonsuz döngüye (infinite loop) girmesini nasıl engelliyorsun?"
> **İdeal Cevap Yaklaşımı:**
> "Ajanların en büyük zaafı, bir araçtan beklediği sonucu alamadığında aynı parametrelerle aynı aracı tekrar tekrar çağırıp token tüketmesidir. Biz üç katmanlı bir sigorta kurduk:
> 1. **Adım Sayacı Kısıtı (Step Budget):** Ajan maksimum 5 adıma (`max_steps=5`) ulaşırsa döngü zorla sonlandırılır ve eldeki son gözlemle nihai cevap üretilir.
> 2. **Semantik Eylem Tekrarı Tespiti (Action Deduplication):** Eğer model bir önceki adımda çağırdığı araç ve parametrelerin aynısını çağırırsa, sistem modeli uyarır: 'Bu aracı aynı parametrelerle zaten denedin ve şu sonucu aldın, farklı bir yaklaşım dene.'
> 3. **Format Bozulma Kurtarıcısı (Fallback Heuristic):** Eğer model JSON formatını bozup serbest metin üretirse, regex tabanlı niyet çıkarıcı devreye girerek süreci güvenli bir final cevaba bağlar."

### S10. "Ajanın terminalde zararlı bir komut çalıştırmasını nasıl engelliyorsunuz? 'rm -rf' gibi komutlara karşı savunmanız ne?"
> **İdeal Cevap Yaklaşımı:**
> "İki katmanlı güvenlik yaklaşımı uyguluyoruz:
> 1. **Deterministik Kara Liste (Deterministic Guardrails):** Modelin ürettiği terminal komutu çalıştırılmadan önce `guardrails.py` filtresinden geçer. `rm -rf`, disk formatlama (`mkfs`), fork bomb veya tehlikeli ağ komutları tespit edilirse komut terminale hiç iletilmeden bloke edilir.
> 2. **İnsan Onayı (Human-In-The-Loop - HITL):** Kritik komutlarda (örneğin dosya üzerine yazma veya paket kurma) ajan doğrudan eyleme geçemez. İstemciye bir `PENDING_APPROVAL` kaydı gönderilir ve kullanıcı arayüzden onay verene kadar eylem bekletilir."

---

## Bölüm 5: Ürünleştirme, Lisanslama & Tersine Mühendislik

### S11. "Python açık kaynaklı ve yorumlanan (interpreted) bir dildir. Müşterinin bilgisayarına kurulan yazılımın kaynak kodlarını çalmasını nasıl engelledin?"
> **İdeal Cevap Yaklaşımı:**
> "Piyasadaki en yaygın hata PyInstaller kullanmaktır. PyInstaller `.pyc` bayt kodlarını bir zip arşivinde toplar ve `uncompyle6` gibi araçlarla birkaç saniyede orijinal kod geri elde edilir.
> Biz **Nuitka** derleyicisini kullandık. Nuitka; Python kodunu, bağımlılıkları ve fonksiyonları doğrudan C++ koduna çevirir ve ardından GCC/MSVC ile makine ikili dosyasına (`.so` / `.pyd` / native binary) derler. Ortada tek bir `.py` dosyası kalmaz.
> *Dürüst bir mühendislik şerhi düşmek gerekir:* Hiçbir derleme tersine mühendisliği imkansız kılmaz; IDA Pro veya Ghidra ile binary analizi yapılabilir. Ancak Nuitka, kod çalma maliyetini '5 saniyelik sıradan bir işlem' olmaktan çıkarıp 'aylar süren ileri seviye tersine mühendislik' seviyesine yükseltir."

### S12. "Lisanslama sisteminiz internet bağlantısı olmadan (offline) nasıl çalışıyor? Kullanıcı saati geri alarak deneme sürümünü uzatamaz mı?"
> **İdeal Cevap Yaklaşımı:**
> "Lisanslama sistemimiz **Node-Locked (Donanım Kilitli)** ve **Kriptografik Zaman Kapsüllü** olarak çalışır:
> - Müşterinin anakart BIOS UUID'si ve CPU kimliğinden tuzlanmış bir SHA-256 donanım parmak izi çıkarılır. Lisans anahtarı bu kimliğe kilitlenir; dosya başka bilgisayara kopyalansa bile çalışmaz.
> - Lisans anahtarının içinde lisans kademesi (`TRIAL`, `MONTH`, `YEAR1`, `LIFET`) ve son kullanma tarihi HMAC-SHA256 ile imzalanmıştır. İnternet olmasa bile yerel matematiksel formülle doğrulanır.
> - Saat sahtekarlığına karşı ise yerel 'Last-Seen Timestamp' kontrolü bulunur; sistem saati son çalışma zamanından geriye alınmışsa lisans motoru manipülasyonu tespit edip kendini kilitler."

---

## Bölüm 6: Davranışsal & Mühendislik Olgunluğu

### S13. "Bu projeyi yaparken karşılaştığın en büyük teknik engel neydi ve bunu nasıl aştın?"
> **İdeal Cevap Yaklaşımı:**
> "En kritik sorun, Rust motorundaki ilkel tokenizer ile modern Qwen 2.5 modeli arasındaki uyumsuzluktu. Qwen 152k kelimelik BPE sözlüğü kullandığı için model ilk başta tamamen anlamsız karakterler ve sonsuz döngüler üretiyordu.
> İlk başta sorunun model ağırlıklarında (quantization) olduğunu düşündüm. Ancak tensor çıktılarını incelediğimde matris çarpımlarının doğru olduğunu, sorunun token-id eşleşmesindeki kaymadan kaynaklandığını tespit ettim. 
> Rust tarafına sıfırdan 152k BPE tokenizer yazmak yerine, C++ AVX2 optimize edilmiş `llama.cpp` çekirdeğini entegre ettik. Böylece hem Türkçe dilbilgisi hem de kod blokları mükemmel bir doğruluğa kavuştu."

### S14. "Bugün bu projeye sıfırdan başlasaydın, neyi farklı yapardın?"
> **İdeal Cevap Yaklaşımı:**
> "İlk aşamada model çıkarımını bağımsız bir Rust binary CLI üzerinden çağırmayı denemiştim. Her sorguda binary'yi alt süreç (`subprocess`) olarak başlatmak, mmap kullansak bile süreç oluşturma (process spawn) gecikmesi yaratıyordu. 
> Baştan başlasaydım, en baştan itibaren çıkarım motorunu doğrudan C-FFI / Python süreci içine gömerdim. Bu sayede hem streaming yanıtını SSE ile çok daha temiz aldık hem de süreçler arası IPC yükünü tamamen ortadan kaldırmış olduk."

---

<div align="center">
<b>AURA-CORE Mülakat Hazırlık Dokümantasyonu</b><br>
<i>Bu rehber, teknik mülakatlarda ezber kalıplar sunmak için değil; mimari kararların arkasındaki derin 'Neden?' sorularına mühendislik dürüstlüğüyle yanıt verebilmeniz için hazırlanmıştır.</i>
</div>

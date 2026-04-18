"""
brand_logo_detector.py  —  v5 FINAL
=====================================
Pipeline order (strict):

  METHOD 1: EasyOCR on trunk area
            → reads "VOLVO", "CRETA", "HYUNDAI", "DZIRE", "SUZUKI" etc.
            → if found: brand + model confirmed, is_estimated=False

  METHOD 2: Smart probability guess
            → uses (color, body_type) → probability table
            → uses brand+body_type → correct model (Hyundai+SUV=Creta, not Verna!)
            → is_estimated=True, shown as "Hyundai*" in UI

NOTE: Badge shape detection removed — too many false positives on rear-view frames.
      OCR is reliable and catches all major brands from trunk text.
"""

import cv2
import numpy as np
from typing import Optional, Dict, List, Tuple

# ── Brand → Model list ────────────────────────────────────────
BRAND_MODEL_MAP: Dict[str, List[str]] = {
    'HYUNDAI':       ['VERNA','CRETA','I20','I10','VENUE','TUCSON','EXTER','ALCAZAR','AURA','SANTRO'],
    'HONDA':         ['CITY','AMAZE','WRV','ELEVATE','JAZZ','BRV'],
    'TATA':          ['NEXON','HARRIER','SAFARI','PUNCH','ALTROZ','TIAGO','TIGOR','CURVV'],
    'MARUTI':        ['SWIFT','BALENO','DZIRE','ERTIGA','BREZZA','FRONX','JIMNY','CIAZ',
                      'ALTO','IGNIS','CELERIO','WAGON','GRAND VITARA'],
    'SUZUKI':        ['SWIFT','BALENO','DZIRE','ERTIGA','BREZZA'],
    'MAHINDRA':      ['SCORPIO','THAR','XUV700','XUV300','XUV400','BOLERO','BE6','KUV','MARAZZO'],
    'TOYOTA':        ['INNOVA','FORTUNER','CAMRY','GLANZA','HYRYDER','URBAN CRUISER','ETIOS','COROLLA'],
    'KIA':           ['SELTOS','SONET','CARNIVAL','EV6','CARENS'],
    'VOLKSWAGEN':    ['POLO','VENTO','TAIGUN','VIRTUS','TIGUAN'],
    'SKODA':         ['OCTAVIA','SUPERB','KUSHAQ','SLAVIA','KODIAQ'],
    'MG':            ['HECTOR','ASTOR','COMET','GLOSTER','ZS','WINDSOR'],
    'RENAULT':       ['KWID','KIGER','DUSTER','TRIBER'],
    'NISSAN':        ['MAGNITE','KICKS','TERRANO','SUNNY','MICRA'],
    'FORD':          ['ECOSPORT','ENDEAVOUR','ASPIRE','FIGO'],
    'JEEP':          ['COMPASS','MERIDIAN','WRANGLER'],
    'CITROEN':       ['C3','C5','AIRCROSS','BASALT'],
    'BMW':           ['X1','X3','X5','X7','320','520','M3','M5'],
    'AUDI':          ['A4','A6','Q3','Q5','Q7','Q8'],
    'MERCEDES':      ['GLA','GLC','GLE','C-CLASS','E-CLASS','S-CLASS'],
    'VOLVO':         ['V60','XC40','XC60','XC90','S60','S90','V90'],
    'LEXUS':         ['NX','RX','ES','LS'],
    'LAND ROVER':    ['DISCOVERY','DEFENDER','RANGE ROVER'],
    'PORSCHE':       ['CAYENNE','MACAN','PANAMERA'],
    'BAJAJ':         ['PULSAR','DOMINAR','AVENGER'],
    'HERO':          ['SPLENDOR','GLAMOUR','PASSION','XPULSE'],
    'TVS':           ['APACHE','JUPITER','NTORQ','RAIDER'],
    'ROYAL ENFIELD': ['CLASSIC','BULLET','METEOR','HUNTER'],
}

MODEL_TO_BRAND: Dict[str, str] = {
    m: brand for brand, models in BRAND_MODEL_MAP.items() for m in models
}

# Given (brand, body_type) → most likely model
# CRITICAL: this stops Hyundai always returning "Verna"
BRAND_BODY_TO_MODEL: Dict[str, Dict[str, str]] = {
    'HYUNDAI':    {'SUV':'Creta',    'Hatchback':'I20',    'Sedan':'Verna',    'MPV':'Alcazar',    'Car':'Verna'},
    'HONDA':      {'SUV':'Elevate',  'Hatchback':'Jazz',   'Sedan':'City',     'MPV':'BRV',        'Car':'City'},
    'TATA':       {'SUV':'Nexon',    'Hatchback':'Altroz', 'Sedan':'Tigor',    'MPV':'Safari',     'Car':'Tiago'},
    'MARUTI':     {'SUV':'Brezza',   'Hatchback':'Swift',  'Sedan':'Dzire',    'MPV':'Ertiga',     'Car':'Swift'},
    'SUZUKI':     {'SUV':'Brezza',   'Hatchback':'Swift',  'Sedan':'Dzire',    'MPV':'Ertiga',     'Car':'Swift'},
    'MAHINDRA':   {'SUV':'Scorpio',  'Hatchback':'Unknown','Sedan':'Unknown',  'MPV':'Marazzo',    'Car':'Unknown'},
    'TOYOTA':     {'SUV':'Fortuner', 'Hatchback':'Glanza', 'Sedan':'Camry',    'MPV':'Innova',     'Car':'Glanza'},
    'KIA':        {'SUV':'Seltos',   'Hatchback':'Unknown','Sedan':'Unknown',  'MPV':'Carens',     'Car':'Sonet'},
    'VOLKSWAGEN': {'SUV':'Taigun',   'Hatchback':'Polo',   'Sedan':'Virtus',   'MPV':'Unknown',    'Car':'Polo'},
    'SKODA':      {'SUV':'Kushaq',   'Hatchback':'Unknown','Sedan':'Slavia',   'MPV':'Unknown',    'Car':'Slavia'},
    'MG':         {'SUV':'Hector',   'Hatchback':'Unknown','Sedan':'Unknown',  'MPV':'Unknown',    'Car':'Astor'},
    'RENAULT':    {'SUV':'Kiger',    'Hatchback':'Kwid',   'Sedan':'Unknown',  'MPV':'Triber',     'Car':'Kwid'},
    'NISSAN':     {'SUV':'Magnite',  'Hatchback':'Micra',  'Sedan':'Sunny',    'MPV':'Unknown',    'Car':'Micra'},
    'FORD':       {'SUV':'Ecosport', 'Hatchback':'Figo',   'Sedan':'Aspire',   'MPV':'Endeavour',  'Car':'Figo'},
    'JEEP':       {'SUV':'Compass',  'Hatchback':'Unknown','Sedan':'Unknown',  'MPV':'Meridian',   'Car':'Compass'},
    'BMW':        {'SUV':'X3',       'Hatchback':'Unknown','Sedan':'320',      'MPV':'Unknown',    'Car':'320'},
    'AUDI':       {'SUV':'Q5',       'Hatchback':'Unknown','Sedan':'A4',       'MPV':'Unknown',    'Car':'A4'},
    'MERCEDES':   {'SUV':'GLC',      'Hatchback':'Unknown','Sedan':'C-Class',  'MPV':'Unknown',    'Car':'C-Class'},
    'VOLVO':      {'SUV':'XC60',     'Hatchback':'Unknown','Sedan':'S60',      'MPV':'Unknown',    'Car':'S60'},
}

# (color, body_type) → [(brand, model, weight)] — used as fallback only
INDIA_CAR_PROBS: Dict[tuple, List[tuple]] = {
    ('White',  'Sedan'):     [('Maruti','Dzire',30),   ('Honda','City',20),     ('Hyundai','Verna',20),  ('Tata','Tigor',15),    ('Toyota','Etios',15)],
    ('Silver', 'Sedan'):     [('Hyundai','Verna',25),  ('Honda','City',20),     ('Maruti','Dzire',20),   ('Tata','Tigor',15),    ('Skoda','Slavia',20)],
    ('Gray',   'Sedan'):     [('Hyundai','Verna',28),  ('Honda','City',22),     ('Maruti','Dzire',20),   ('Skoda','Slavia',15),  ('Tata','Tigor',15)],
    ('Black',  'Sedan'):     [('Honda','City',28),     ('Skoda','Slavia',22),   ('Hyundai','Verna',22),  ('Maruti','Dzire',15),  ('Toyota','Camry',13)],
    ('Blue',   'Sedan'):     [('Hyundai','Verna',28),  ('Honda','City',25),     ('Maruti','Dzire',22),   ('Tata','Tigor',15),    ('Skoda','Slavia',10)],
    ('Red',    'Sedan'):     [('Hyundai','Verna',30),  ('Honda','City',25),     ('Maruti','Dzire',25),   ('Tata','Tigor',20)],

    ('White',  'Hatchback'): [('Maruti','Swift',35),   ('Hyundai','I20',25),    ('Tata','Altroz',20),    ('Maruti','Baleno',20)],
    ('Silver', 'Hatchback'): [('Maruti','Swift',30),   ('Hyundai','I20',28),    ('Tata','Altroz',22),    ('Maruti','Baleno',20)],
    ('Gray',   'Hatchback'): [('Hyundai','I20',32),    ('Maruti','Swift',25),   ('Tata','Altroz',25),    ('Maruti','Baleno',18)],
    ('Red',    'Hatchback'): [('Maruti','Swift',40),   ('Hyundai','I20',28),    ('Tata','Altroz',20),    ('Maruti','Baleno',12)],
    ('Blue',   'Hatchback'): [('Maruti','Swift',35),   ('Hyundai','I20',30),    ('Tata','Altroz',22),    ('Maruti','Baleno',13)],
    ('Black',  'Hatchback'): [('Hyundai','I20',32),    ('Maruti','Swift',25),   ('Tata','Altroz',25),    ('Maruti','Baleno',18)],

    ('White',  'SUV'):       [('Hyundai','Creta',22),  ('Tata','Nexon',20),     ('Maruti','Brezza',18),  ('Kia','Seltos',15),    ('Mahindra','Scorpio',10),('Toyota','Fortuner',8), ('MG','Hector',7)],
    ('Silver', 'SUV'):       [('Hyundai','Creta',22),  ('Tata','Nexon',20),     ('Maruti','Brezza',18),  ('Kia','Seltos',15),    ('Toyota','Fortuner',13), ('Mahindra','Thar',12)],
    ('Gray',   'SUV'):       [('Hyundai','Creta',25),  ('Tata','Nexon',20),     ('Maruti','Brezza',18),  ('Kia','Seltos',15),    ('MG','Hector',12),       ('Toyota','Fortuner',10)],
    ('Black',  'SUV'):       [('Mahindra','Scorpio',18),('Hyundai','Creta',15), ('Tata','Nexon',15),     ('Kia','Seltos',12),    ('Toyota','Fortuner',12), ('MG','Hector',10),     ('Jeep','Compass',9),('BMW','X3',5),('Volvo','XC60',4)],
    ('Red',    'SUV'):       [('Tata','Nexon',30),     ('Hyundai','Creta',22),  ('Maruti','Brezza',18),  ('Kia','Sonet',15),     ('Mahindra','Thar',15)],
    ('Blue',   'SUV'):       [('Hyundai','Venue',22),  ('Tata','Nexon',22),     ('Kia','Sonet',18),      ('Maruti','Brezza',18), ('Hyundai','Creta',12),   ('MG','Astor',8)],
    ('Orange', 'SUV'):       [('Tata','Nexon',40),     ('Mahindra','Thar',30),  ('Kia','Sonet',30)],

    ('White',  'MPV'):       [('Maruti','Ertiga',30),  ('Toyota','Innova',25),  ('Kia','Carens',20),     ('Mahindra','Marazzo',15),('Renault','Triber',10)],
    ('Silver', 'MPV'):       [('Toyota','Innova',35),  ('Maruti','Ertiga',25),  ('Kia','Carens',20),     ('Mahindra','Marazzo',20)],
    ('White',  'Motorcycle'):[('Honda','Activa',30),   ('Bajaj','Pulsar',20),   ('TVS','Apache',20),     ('Hero','Splendor',15), ('Royal Enfield','Classic',15)],
    ('Black',  'Motorcycle'):[('Royal Enfield','Classic',30),('Bajaj','Pulsar',25),('TVS','Apache',20),  ('Hero','Splendor',15), ('Honda','CB',10)],
}

# Color-only brand probability (used when body_type is unknown or too vague)
COLOR_BRAND_PROBS: Dict[str, List[tuple]] = {
    'White':  [('Maruti',30),('Hyundai',22),('Tata',18),('Honda',15),('Toyota',10),('Kia',5)],
    'Silver': [('Hyundai',28),('Maruti',22),('Honda',18),('Tata',16),('Skoda',10),('Toyota',6)],
    'Gray':   [('Hyundai',30),('Tata',22),('Maruti',18),('Honda',15),('Skoda',10),('MG',5)],
    'Black':  [('Mahindra',20),('Hyundai',18),('Tata',18),('Honda',15),('Toyota',12),('BMW',10),('Jeep',7)],
    'Red':    [('Tata',28),('Maruti',25),('Hyundai',22),('Honda',15),('Kia',10)],
    'Blue':   [('Maruti',25),('Hyundai',25),('Tata',20),('Honda',15),('Kia',15)],
    'Orange': [('Tata',40),('Mahindra',30),('Maruti',20),('Kia',10)],
    'Green':  [('Tata',30),('Maruti',25),('Mahindra',25),('Hyundai',20)],
}

# Normalize vague body type labels to table keys
BODY_TYPE_NORMALIZE: Dict[str, str] = {
    'Car':     'Sedan',    # BodyTypeDetector "Car" → try Sedan first
    'Compact': 'Hatchback',
    'Wagon':   'SUV',
    'Coupe':   'Sedan',
    'Pickup':  'SUV',
    'Truck':   'SUV',
}

OCR_CORRECTIONS = {
    'HYUNDAL':'HYUNDAI','HYUNDA1':'HYUNDAI','H0NDA':'HONDA',
    'SUZUK1':'SUZUKI','T0Y0TA':'TOYOTA','T0YOTA':'TOYOTA',
    'MAHINDFIA':'MAHINDRA','V0LVO':'VOLVO','V0LKSWAGEN':'VOLKSWAGEN',
    'VERN4':'VERNA','CR3TA':'CRETA','NEX0N':'NEXON',
    'SC0RPIO':'SCORPIO','SWLFT':'SWIFT','BALEN0':'BALENO',
    'DZ1RE':'DZIRE','DZlRE':'DZIRE','DZLRE':'DZIRE',
    'MAR UTI':'MARUTI','MAR-UTI':'MARUTI','BALENC':'BALENO',
    'MARC':'MARUTI','D51RE':'DZIRE','0CTAVIA':'OCTAVIA',
}


def _brand_body_to_model(brand: str, body_type: str) -> str:
    """Pick the correct model for a brand given body type. Never just picks index 0."""
    brand_up = brand.upper()
    body_map  = BRAND_BODY_TO_MODEL.get(brand_up, {})
    # Normalize body type
    bt = body_type
    if bt in ('Car', 'Sedan', 'Hatchback', 'Compact'):
        bt = body_map.get(bt) or body_map.get('Car', 'Unknown')
    else:
        bt = body_map.get(bt) or body_map.get('Car', 'Unknown')
    return bt if bt else 'Unknown'


def smart_guess(color: str, body_type: str) -> Tuple[str, str, float]:
    """
    3-tier probability guess:
    Tier 1: (color, body_type) exact match in INDIA_CAR_PROBS
    Tier 2: normalize body_type alias ('Car'→'Sedan') and retry
    Tier 3: color-only brand guess, model="—" (honest fallback)

    Confidence capped at 0.45. Never pins a specific wrong model.
    """
    c = color.strip().title() if color else "Unknown"
    b = body_type.strip()     if body_type else "Unknown"

    # Tier 1 + 2: try exact body, then normalized, then Car→Sedan→Hatchback
    candidates = None
    for try_body in [b, BODY_TYPE_NORMALIZE.get(b, b),
                     'Sedan'     if b == 'Car' else None,
                     'Hatchback' if b == 'Car' else None]:
        if try_body is None:
            continue
        candidates = INDIA_CAR_PROBS.get((c, try_body))
        if candidates:
            break
    
    if candidates:
        best  = max(candidates, key=lambda x: x[2])
        total = sum(x[2] for x in candidates)
        conf  = round((best[2] / total) * 0.45, 2)
        # Only pin a specific model if it's a clear winner (conf ≥ 8%)
        if conf >= 0.08:
            return best[0], best[1], conf

    # Tier 3: color-only brand, no specific model
    brand_probs = COLOR_BRAND_PROBS.get(c,
                  [('Maruti',30),('Hyundai',25),('Tata',25),('Honda',20)])
    best_brand  = max(brand_probs, key=lambda x: x[1])
    total       = sum(x[1] for x in brand_probs)
    conf        = round((best_brand[1] / total) * 0.35, 2)
    return best_brand[0], "—", conf


class OCRBrandDetector:
    def __init__(self, reader=None):
        self._reader = reader
        self._tried  = False

    def set_reader(self, reader):
        self._reader = reader

    def _ensure_reader(self) -> bool:
        if self._reader:  return True
        if self._tried:   return False
        self._tried = True
        try:
            import easyocr
            self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            return True
        except Exception:
            return False

    def detect(self, car_crop: np.ndarray) -> Optional[Tuple[str, str, float]]:
        """Returns (brand, model, confidence) or None."""
        if not self._ensure_reader() or car_crop is None or car_crop.size == 0:
            return None
        try:
            h, w = car_crop.shape[:2]
            # Search entire upper 80% (trunk text location varies)
            region = car_crop[max(0,int(h*0.02)):int(h*0.82),
                              max(0,int(w*0.03)):int(w*0.97)]
            if region.size == 0:
                return None

            scale = max(2, min(5, 300 // max(min(region.shape[:2]), 1)))
            large = cv2.resize(region,
                               (region.shape[1]*scale, region.shape[0]*scale),
                               interpolation=cv2.INTER_CUBIC)

            gray  = cv2.cvtColor(large, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enh   = clahe.apply(gray)
            inv   = cv2.bitwise_not(enh)

            all_texts = []
            for img_var in [large,
                            cv2.cvtColor(enh, cv2.COLOR_GRAY2BGR),
                            cv2.cvtColor(inv, cv2.COLOR_GRAY2BGR)]:
                try:
                    for _, text, conf in self._reader.readtext(img_var, detail=1,
                                                               paragraph=False):
                        if conf > 0.20 and len(text.strip()) >= 2:
                            all_texts.append(text.upper().strip())
                except Exception:
                    pass

            return self._match(list(set(all_texts)))
        except Exception as e:
            print(f"OCRBrandDetector: {e}")
            return None

    def _match(self, texts: List[str]) -> Optional[Tuple[str, str, float]]:
        brand_found = model_found = None
        best_conf   = 0.0

        for raw in texts:
            text = raw
            for wrong, right in OCR_CORRECTIONS.items():
                text = text.replace(wrong, right)
            clean = text.replace(' ','').replace('-','').replace('.','')

            for brand in BRAND_MODEL_MAP:
                bc = brand.replace(' ','')
                if bc == clean or (bc in clean and len(clean) <= len(bc)+3):
                    if len(clean) >= 3:
                        brand_found = brand.title()
                        best_conf   = max(best_conf, 0.82)

            for model, brand in MODEL_TO_BRAND.items():
                mc = model.replace(' ','').replace('-','')
                if mc == clean or (mc in clean and len(clean) <= len(mc)+3):
                    if len(clean) >= 3:
                        model_found = model.title()
                        if brand_found is None:
                            brand_found = brand.title()
                        best_conf = max(best_conf, 0.90)

        if brand_found or model_found:
            return (brand_found or "Unknown", model_found or "Unknown", best_conf)
        return None


class BrandLogoDetector:
    """
    detect_full() → (brand, model, confidence, is_estimated)
      is_estimated=False : confirmed by OCR  → show "Hyundai Creta"
      is_estimated=True  : probability guess → show "Hyundai* Creta*"
    """

    def __init__(self, ocr_reader=None):
        self._ocr   = OCRBrandDetector(ocr_reader)
        self._cache: Dict[int, Tuple[str,str,float,bool]] = {}

    def set_ocr_reader(self, reader):
        self._ocr.set_reader(reader)

    def detect_full(self,
                    frame:      np.ndarray,
                    car_bbox:   list,
                    car_id:     Optional[int] = None,
                    color:      str = "Unknown",
                    body_type:  str = "Unknown",
                    plate_text: str = "",
                    use_cache:  bool = True
                    ) -> Tuple[str, str, float, bool]:
        """Returns (brand, model, confidence, is_estimated)."""

        if use_cache and car_id is not None and car_id in self._cache:
            return self._cache[car_id]

        brand = model = "Unknown"
        conf  = 0.0
        is_est = False

        try:
            x1,y1,x2,y2 = [int(v) for v in car_bbox[:4]]
            fh,fw = frame.shape[:2]
            crop = frame[max(0,y1):min(fh,y2), max(0,x1):min(fw,x2)]

            if crop.size > 0:
                # Method 1: OCR
                ocr_result = self._ocr.detect(crop)
                if ocr_result:
                    brand, model, conf = ocr_result
                    is_est = False

                    # OCR found brand but not model → use body_type to pick model
                    if model == "Unknown" and brand != "Unknown":
                        model  = _brand_body_to_model(brand, body_type)
                        is_est = (model == "Unknown")

        except Exception as e:
            print(f"BrandLogoDetector: {e}")

        # Method 2: Smart probability guess (OCR failed)
        if brand == "Unknown":
            brand, model, conf = smart_guess(color, body_type)
            is_est = True

        # If brand known but model still unknown, try body_type lookup
        if model == "Unknown" and brand != "Unknown":
            model  = _brand_body_to_model(brand, body_type)
            is_est = True

        out = (brand, model, conf, is_est)
        if use_cache and car_id is not None:
            self._cache[car_id] = out
        return out

    def detect(self, frame, car_bbox, car_id=None, color="Unknown",
               body_type="Unknown", plate_text="", use_cache=True):
        """Backward-compatible: returns (brand, model, confidence)."""
        b, m, c, _ = self.detect_full(frame, car_bbox, car_id, color,
                                       body_type, plate_text, use_cache)
        return b, m, c

    def clear_cache(self):
        self._cache.clear()


if __name__ == "__main__":
    import cv2 as _cv2

    det = BrandLogoDetector()

    # Test smart_guess directly (no OCR needed)
    print("=== smart_guess() tests ===")
    for color, body, note in [
        ("Black",  "SUV",      "Volvo V60 / Scorpio"),
        ("White",  "SUV",      "Hyundai Creta / Brezza"),
        ("White",  "Sedan",    "Maruti Dzire"),
        ("Silver", "Sedan",    "Hyundai Verna"),
        ("Red",    "Hatchback","Maruti Swift"),
        ("White",  "MPV",      "Toyota Innova"),
    ]:
        b, m, c = smart_guess(color, body)
        print(f"  ({color:7s}, {body:10s}) → {b} {m} ({c:.0%})  [{note}]")

    print("\n=== _brand_body_to_model() tests ===")
    for brand, body, expected in [
        ("HYUNDAI",  "SUV",      "Creta"),
        ("HYUNDAI",  "Sedan",    "Verna"),
        ("HYUNDAI",  "Hatchback","I20"),
        ("MARUTI",   "Sedan",    "Dzire"),
        ("TATA",     "SUV",      "Nexon"),
        ("TOYOTA",   "MPV",      "Innova"),
    ]:
        result = _brand_body_to_model(brand, body)
        ok = "✅" if result == expected else "❌"
        print(f"  {ok} {brand:12s} + {body:10s} → {result} (expected {expected})")

    print("\n=== Full detect_full() with real images ===")
    tests = [
        ('/mnt/user-data/uploads/1772876465790_image.png', 'KA01MS7103', 'Black', 'SUV',      'Volvo V60'),
        ('/mnt/user-data/uploads/1772876499099_image.png', 'KA05MU0712', 'White', 'SUV',      'Hyundai Creta'),
        ('/mnt/user-data/uploads/1772876526491_image.png', 'KA plate',   'White', 'Sedan',    'Maruti Dzire'),
    ]
    for path, plate, color, body, expected in tests:
        img = _cv2.imread(path)
        h, w = img.shape[:2]
        brand, model, conf, est = det.detect_full(
            img, [0,0,w,h], car_id=None,
            color=color, body_type=body, plate_text=plate)
        mark = "*" if est else ""
        exp_brand = expected.split()[0].upper()
        exp_model = expected.split()[-1].upper()
        ok = "✅" if (exp_brand in brand.upper() or exp_model in model.upper()) else "❌"
        print(f"  {ok} {expected:20s} → {brand+mark} {model+mark} ({conf:.0%}) [est={est}]")
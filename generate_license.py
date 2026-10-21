#!/usr/bin/env python3
# ==============================================================================
# 👑 AIAssistant - Patron Lisans Üretim Aracı (License Key Generator)
# Müşterinin donanım kimliğine (Hardware ID) özel, kriptografik lisans anahtarı üretir.
# ==============================================================================

import sys
import os
import argparse

# Proje dizinlerini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "Rust-Python-Vector-Engine")))

from api_server.app.core.licensing import license_manager, TIER_CONFIG

def main():
    parser = argparse.ArgumentParser(
        description="AIAssistant Ticari Lisans Üreticisi (Yalnızca Satıcı Kullanımı İçin)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Kullanım Örnekleri:
  python generate_license.py --hw 68EC-55C5-76EB-F823 --tier trial
  python generate_license.py --hw 68EC-55C5-76EB-F823 --tier month
  python generate_license.py --hw 68EC-55C5-76EB-F823 --tier year
  python generate_license.py --hw 68EC-55C5-76EB-F823 --tier lifetime
        """
    )
    parser.add_argument("--hw", type=str, required=True, help="Müşterinin bildirdiği Donanım Kimliği (Örn: 68EC-55C5-76EB-F823)")
    parser.add_argument("--tier", type=str, default="trial", choices=["trial", "month", "year", "lifetime"], help="Lisans kademesi")
    parser.add_argument("--days", type=int, default=None, help="Özel gün sayısı tanımlamak isterseniz (Opsiyonel)")

    args = parser.parse_args()

    tier_map = {
        "trial": "TRIAL",
        "month": "MONTH",
        "year": "YEAR1",
        "lifetime": "LIFET"
    }

    selected_tier = tier_map[args.tier.lower()]

    try:
        license_key = license_manager.generate_license_key(
            hardware_fingerprint=args.hw,
            tier=selected_tier,
            custom_days=args.days
        )
        tier_info = TIER_CONFIG[selected_tier]

        print("\n" + "=" * 65)
        print("🎉 LİSANS ANAHTARI BAŞARIYLA ÜRETİLDİ!")
        print("=" * 65)
        print(f"🖥️  Müşteri Donanım Kimliği : {args.hw.strip().upper()}")
        print(f"📦 Lisans Kademesi         : {tier_info['name']} ({selected_tier})")
        if selected_tier == "LIFET":
            print(f"⏳ Geçerlilik Süresi       : Sınırsız / Ömür Boyu (Perpetual)")
        else:
            days = args.days or tier_info['days']
            print(f"⏳ Geçerlilik Süresi       : {days} Gün")
        print("-" * 65)
        print(f"🔑 LİSANS ANAHTARI (Müşteriye İletilecek):\n\n    {license_key}\n")
        print("=" * 65 + "\n")

    except Exception as e:
        print(f"\n❌ Lisans üretilirken hata oluştu: {e}\n", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

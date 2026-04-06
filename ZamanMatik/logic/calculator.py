from datetime import date

from models.case_data import CaseData
from utils.date_utils import (
    add_period_to_date_legal,
    apply_age_reduction,
    calculate_period_difference,
    date_diff_days,
    format_date,
    format_period,
    format_period_tuple,
    multiply_period,
)


class LimitationCalculator:
    """
    Türk Ceza Kanunu 66. ve 67. maddelerine göre dava zamanaşımı hesaplar.
    Hukuk mantığına uygun olarak her ay 30 gün kabul edilir.
    """

    def __init__(self):
        self.base_periods = {
            "Ağırlaştırılmış müebbet": (30, 0, 0),
            "Müebbet": (25, 0, 0),
            "20 yıl ve üzeri hapis": (20, 0, 0),
            "5 yıldan fazla - 20 yıldan az hapis": (15, 0, 0),
            "5 yıl veya daha az hapis": (8, 0, 0),
            "Adlî para cezası": (8, 0, 0),
        }

    def calculate(self, case_data: CaseData):
        """
        Çoklu kesilme halinde her geçerli kesilme tarihi, o anda yürüyen süreyi
        yeniden başlatır. Ancak nihai tarih olağanüstü zamanaşımı sınırını aşamaz.
        """
        details = ["<h3>Dava Zamanaşımı Hesaplama Detayları</h3>"]
        section_number = 1

        base_period = self.base_periods[case_data.ceza_turu]
        base_years, base_months, base_days = base_period

        details.append(f"<p><b>{section_number}. Temel Zamanaşımı Süresi (TCK 66/1)</b></p>")
        details.append(f"<p>Ceza türü: {case_data.ceza_turu}</p>")
        details.append(f"<p>Temel zamanaşımı süresi: {format_period_tuple(base_period)}</p>")
        section_number += 1

        final_period = base_period
        if case_data.fail_yasi < 18:
            details.append(f"<p><b>{section_number}. Çocuk Fail İndirimi (TCK 66/2)</b></p>")
            details.append(f"<p>Failin yaşı: {case_data.fail_yasi}</p>")

            if 12 <= case_data.fail_yasi < 15:
                final_period = apply_age_reduction(base_years, base_months, base_days, "12-15")
                details.append("<p>12-15 yaş arası: Sürenin yarısı uygulanır</p>")
                details.append(f"<p>Hesaplama: {format_period_tuple(base_period)} × (1/2) = {format_period_tuple(final_period)}</p>")
            elif 15 <= case_data.fail_yasi < 18:
                final_period = apply_age_reduction(base_years, base_months, base_days, "15-18")
                details.append("<p>15-18 yaş arası: Sürenin üçte ikisi uygulanır</p>")
                details.append(f"<p>Hesaplama: {format_period_tuple(base_period)} × (2/3) = {format_period_tuple(final_period)}</p>")

            section_number += 1

        final_years, final_months, final_days = final_period

        max_period = multiply_period(final_years, final_months, final_days, 1.5)
        max_years, max_months, max_days = max_period

        details.append(f"<p><b>{section_number}. Maksimum Süre Hesabı (TCK 67/4)</b></p>")
        details.append("<p>Zamanaşımı kesilse bile toplam süre, asıl sürenin 1.5 katını geçemez:</p>")
        details.append(f"<p>Hesaplama: {format_period_tuple(final_period)} × 1.5 = {format_period_tuple(max_period)}</p>")
        details.append("<p style='background-color: #fff3cd; padding: 8px; border-left: 4px solid #ffc107;'>")
        details.append("<b>Önemli:</b> Ay sayısı 12'yi geçse bile yıla çevrilmez (hukuk mantığı).")
        details.append("</p>")
        section_number += 1

        total_suspension_years = 0
        total_suspension_months = 0
        total_suspension_days = 0

        if case_data.zamanasimi_durdu_mu and case_data.suspension_periods:
            details.append(f"<p><b>{section_number}. Zamanaşımının Durması (TCK 67/1)</b></p>")
            details.append("<p>Durma süreleri (HUKUK MANTIĞI: Her ay 30 gün):</p><ul>")

            for i, (suspension_start, suspension_end) in enumerate(case_data.suspension_periods):
                years, months, days = calculate_period_difference(suspension_start, suspension_end)
                total_suspension_years += years
                total_suspension_months += months
                total_suspension_days += days
                details.append(
                    f"<li>{i+1}. Durma: {format_date(suspension_start)} - {format_date(suspension_end)} ({format_period(years, months, days)})</li>"
                )

            details.append("</ul>")

            if total_suspension_days >= 30:
                extra_months = total_suspension_days // 30
                total_suspension_months += extra_months
                total_suspension_days %= 30

            total_period_str = format_period(total_suspension_years, total_suspension_months, total_suspension_days)
            details.append(f"<p>Toplam durma süresi: {total_period_str}</p>")
            details.append("<p style='background-color: #e0f2fe; padding: 8px; border-left: 4px solid #0284c7;'>")
            details.append("<b>Not:</b> Durma süresi, 30 günlük ay mantığıyla hesaplanır. Ay sayısı yıla çevrilmez.")
            details.append("</p>")
            section_number += 1

        base_expiry_date = add_period_to_date_legal(case_data.suc_tarihi, final_years, final_months, final_days)
        if total_suspension_years or total_suspension_months or total_suspension_days:
            base_expiry_date = add_period_to_date_legal(
                base_expiry_date,
                total_suspension_years,
                total_suspension_months,
                total_suspension_days,
            )

        max_expiry_date = add_period_to_date_legal(case_data.suc_tarihi, max_years, max_months, max_days)
        if total_suspension_years or total_suspension_months or total_suspension_days:
            max_expiry_date = add_period_to_date_legal(
                max_expiry_date,
                total_suspension_years,
                total_suspension_months,
                total_suspension_days,
            )

        valid_interruptions = []
        invalid_interruptions = []
        last_interruption = None
        interruption_within_base_period = False
        running_expiry_date = base_expiry_date

        for interruption_date in sorted(set(case_data.kesilme_tarihleri)):
            comparison_start = last_interruption if last_interruption is not None else case_data.suc_tarihi

            if comparison_start < interruption_date <= running_expiry_date:
                valid_interruptions.append(interruption_date)
                interruption_within_base_period = True
                last_interruption = interruption_date

                restarted_expiry_date = add_period_to_date_legal(
                    interruption_date,
                    final_years,
                    final_months,
                    final_days,
                )
                if total_suspension_years or total_suspension_months or total_suspension_days:
                    restarted_expiry_date = add_period_to_date_legal(
                        restarted_expiry_date,
                        total_suspension_years,
                        total_suspension_months,
                        total_suspension_days,
                    )

                running_expiry_date = min(restarted_expiry_date, max_expiry_date)
            else:
                invalid_interruptions.append(interruption_date)

        if valid_interruptions:
            details.append(f"<p><b>{section_number}. Zamanaşımının Kesilmesi (TCK 67/2 ve 67/3)</b></p>")
            if len(valid_interruptions) > 1:
                details.append("<p>Zamanaşımını kesen ve süreyi yeniden başlatan olaylar:</p>")
                details.append("<ul>")
                for i, interruption_date in enumerate(valid_interruptions):
                    details.append(f"<li>{i+1}. Kesilme tarihi: {format_date(interruption_date)}</li>")
                details.append("</ul>")

            details.append(f"<p>Son kesilme tarihi: {format_date(last_interruption)}</p>")
            details.append("<p style='background-color: #fff3cd; padding: 8px; border-left: 4px solid #ffc107;'>")
            details.append("<b>Önemli:</b> Her geçerli kesilme tarihinde zamanaşımı yeniden başlatılmıştır.")
            details.append(f"<br>İlk temel zamanaşımı bitiş tarihi (kesilme olmasaydı): {format_date(base_expiry_date)}")
            details.append(f"<br>Son geçerli kesilme sonrası dikkate alınan bitiş tarihi: {format_date(running_expiry_date)}")
            details.append("</p>")

            if invalid_interruptions:
                details.append("<p>Geçersiz sayılan kesilme tarihleri:</p>")
                details.append("<ul>")
                for i, interruption_date in enumerate(invalid_interruptions):
                    details.append(
                        f"<li>{i+1}. {format_date(interruption_date)} (o tarihte geçerli zamanaşımı süresi dolmuş olduğu için dikkate alınmadı)</li>"
                    )
                details.append("</ul>")

            section_number += 1
        elif case_data.kesilme_tarihleri:
            details.append(f"<p><b>{section_number}. Zamanaşımının Kesilmesi Kontrolü</b></p>")
            details.append("<p>Girilen kesilme tarihleri:</p>")
            details.append("<ul>")
            for i, interruption_date in enumerate(sorted(set(case_data.kesilme_tarihleri))):
                details.append(f"<li>{i+1}. {format_date(interruption_date)}</li>")
            details.append("</ul>")
            details.append(f"<p>Temel zamanaşımı bitiş tarihi: {format_date(base_expiry_date)}</p>")
            details.append("<p style='background-color: #f8d7da; padding: 8px; border-left: 4px solid #dc3545;'>")
            details.append("<b>Önemli:</b> Girilen kesilme tarihleri, geçerli zamanaşımı süresi içinde kalmadığı için dikkate alınmamıştır.")
            details.append("<br>Bu durumda kesilme zamanaşımını yenileyemez. Sadece temel zamanaşımı süresi esas alınır.")
            details.append("</p>")
            section_number += 1

        if not interruption_within_base_period:
            final_expiry_date = base_expiry_date

            details.append(f"<p><b>{section_number}. Zamanaşımı Bitiş Tarihi Hesabı</b></p>")
            details.append("<p style='background-color: #d1ecf1; padding: 8px; border-left: 4px solid #0c5460;'>")
            details.append("<b>Hesaplama Mantığı:</b> Temel zamanaşımı süresi içinde kesilme olmadığı için, uzamış zamanaşımı (1.5 kat) dikkate alınmaz.")
            details.append("</p>")
            details.append(f"<p>Suç tarihi: {format_date(case_data.suc_tarihi)}</p>")
            details.append(f"<p>Temel zamanaşımı süresi: {format_period_tuple(final_period)}</p>")
            if total_suspension_years or total_suspension_months or total_suspension_days:
                details.append(f"<p>Durma süresi: {format_period(total_suspension_years, total_suspension_months, total_suspension_days)}</p>")
            details.append(f"<p><b>Nihai bitiş tarihi:</b> {format_date(final_expiry_date)}</p>")
        else:
            expiry_from_interruption = running_expiry_date
            final_expiry_date = min(expiry_from_interruption, max_expiry_date)

            details.append(f"<p><b>{section_number}. Zamanaşımı Bitiş Tarihi Hesabı</b></p>")
            details.append("<p style='background-color: #d1ecf1; padding: 8px; border-left: 4px solid #0c5460;'>")
            details.append("<b>Hesaplama Mantığı:</b> Geçerli her kesilme tarihinde zamanaşımı yeniden başlar.")
            details.append("<br>Ancak toplam süre, maksimum süreyi (1.5 kat) geçemez.")
            details.append("</p>")
            details.append(f"<p>Suç tarihi: {format_date(case_data.suc_tarihi)}</p>")
            details.append(f"<p>Son kesilme tarihi: {format_date(last_interruption)}</p>")
            details.append(f"<p>Temel zamanaşımı süresi: {format_period_tuple(final_period)}</p>")
            details.append(f"<p>Maksimum süre (1.5 kat): {format_period_tuple(max_period)}</p>")

            if expiry_from_interruption != final_expiry_date:
                details.append(f"<p>Kesilme tarihinden itibaren bitiş: {format_date(expiry_from_interruption)}</p>")
                details.append(f"<p>Maksimum süreye göre bitiş: {format_date(max_expiry_date)}</p>")
                details.append("<p style='background-color: #fff3cd; padding: 8px;'>")
                details.append("<b>Not:</b> Maksimum süre sınırı aşılmıştır.")
                details.append("</p>")

            details.append(f"<p><b>Nihai bitiş tarihi:</b> {format_date(final_expiry_date)}</p>")

        remaining_days = date_diff_days(case_data.bugun, final_expiry_date)
        is_expired = remaining_days < 0

        return {
            "is_expired": is_expired,
            "expiry_date": final_expiry_date,
            "base_period": base_period,
            "final_period": final_period,
            "max_period": max_period,
            "remaining_days": remaining_days,
            "detailed_html": "".join(details),
            "interruption_within_base": interruption_within_base_period,
            "base_expiry_date": base_expiry_date,
            "case_data": case_data,
            "last_interruption": last_interruption,
            "valid_interruptions": valid_interruptions,
            "invalid_interruptions": invalid_interruptions,
            "total_suspension": (total_suspension_years, total_suspension_months, total_suspension_days),
        }

    def generate_judgment_text(self, result: dict, case_data: CaseData) -> str:
        """
        Zamanaşımı nedeniyle kamu davasının düşmesi durumunda gerekçe + hüküm metni üretir.
        """
        lines = []

        is_child = case_data.fail_yasi < 18
        subject = "suça sürüklenen çocuk" if is_child else "sanık"

        final_period = result["final_period"]
        max_period = result["max_period"]
        final_expiry_date = result["expiry_date"]
        interruption_within_base = result["interruption_within_base"]
        base_expiry_date = result["base_expiry_date"]
        last_interruption = result.get("last_interruption")
        total_susp = result.get("total_suspension", (0, 0, 0))

        is_adli_para = case_data.ceza_turu == "Adlî para cezası"
        is_mubebbet = case_data.ceza_turu == "Müebbet"
        is_agirlas_mubebbet = case_data.ceza_turu == "Ağırlaştırılmış müebbet"

        age_fraction_text = ""
        age_group_text = ""
        if is_child:
            if 12 <= case_data.fail_yasi < 15:
                age_fraction_text = "yarısının"
                age_group_text = "12-15 yaş arası"
            elif 15 <= case_data.fail_yasi < 18:
                age_fraction_text = "üçte ikisinin"
                age_group_text = "15-18 yaş arası"

        tck_madde = "66/2" if is_child else "66/1"

        total_suspension_years, total_suspension_months, total_suspension_days = total_susp

        expiry_from_interruption = None
        max_expiry_date = None
        if interruption_within_base and last_interruption:
            final_years, final_months, final_days = final_period
            expiry_from_interruption = add_period_to_date_legal(
                last_interruption,
                final_years,
                final_months,
                final_days,
            )

            if total_suspension_years or total_suspension_months or total_suspension_days:
                expiry_from_interruption = add_period_to_date_legal(
                    expiry_from_interruption,
                    total_suspension_years,
                    total_suspension_months,
                    total_suspension_days,
                )

            max_years, max_months, max_days = max_period
            max_expiry_date = add_period_to_date_legal(
                case_data.suc_tarihi,
                max_years,
                max_months,
                max_days,
            )

            if total_suspension_years or total_suspension_months or total_suspension_days:
                max_expiry_date = add_period_to_date_legal(
                    max_expiry_date,
                    total_suspension_years,
                    total_suspension_months,
                    total_suspension_days,
                )

        bugun = date.today().strftime("%d/%m/%Y")

        lines.append("\tGEREKÇE:\n\n")
        lines.append(f'\tHer ne kadar {subject} hakkında "……" suçunu işlediği iddiasıyla kamu davası açılmış ise de; ')
        lines.append("dosya kapsamının incelenmesinde, atılı suçun işlendiği iddia olunan tarihin ")
        lines.append(f"{format_date(case_data.suc_tarihi)} olduğu")

        if is_child:
            lines.append(", suça sürüklenen çocuğun suç tarihi itibarıyla ")
            lines.append(f"{age_group_text} grubunda bulunduğu")
            lines.append(", 5237 sayılı TCK'nın 66/2. maddesi gereğince ")
            lines.append(f"TCK'nın 66/1. maddesindeki sürelerin {age_fraction_text} esas alınacağı")

        ceza_text = case_data.ceza_turu
        if not is_adli_para and not is_mubebbet and not is_agirlas_mubebbet:
            ceza_text += " cezasını"

        if is_adli_para:
            lines.append(", suç için öngörülen cezanın adli para cezası gerektirdiği, ")
        elif is_mubebbet:
            lines.append(", suç için öngörülen cezanın müebbet cezasını gerektirdiği, ")
        elif is_agirlas_mubebbet:
            lines.append(", suç için öngörülen cezanın ağırlaştırılmış müebbet cezasını gerektirdiği, ")
        else:
            lines.append(f", suç için öngörülen cezanın üst sınırının {ceza_text} gerektirdiği, ")

        lines.append(f"bu kapsamda olağan zamanaşımı süresinin {format_period_tuple(final_period)}, ")
        lines.append(f"olağanüstü zamanaşımı süresinin ise TCK'nın 67/4. maddesi gereğince {format_period_tuple(max_period)} olduğu anlaşılmıştır.\n")

        lines.append(f"\t{subject.capitalize()} hakkında ")

        if case_data.zamanasimi_durdu_mu and case_data.suspension_periods:
            for i, (start, end) in enumerate(case_data.suspension_periods):
                if i > 0:
                    lines.append("")
                years, months, days = calculate_period_difference(start, end)
                period_str = format_period(years, months, days)
                lines.append(f"{format_date(start)} - {format_date(end)} ({period_str}) tarihleri arasında …… nedeniyle zamanaşımının durduğu, ")

        if last_interruption:
            lines.append(f"zamanaşımını kesen son işlemin ………… ile {format_date(last_interruption)} tarihinde gerçekleştiği, ")
        else:
            lines.append("olağan zamanaşımı süresi içerisinde zamanaşımını kesen bir işlemin bulunmadığı, ")

        ordinary_expiry_date = base_expiry_date
        if interruption_within_base and last_interruption:
            ordinary_expiry_date = expiry_from_interruption

        lines.append(f"buna göre olağan zamanaşımı süresinin {format_date(ordinary_expiry_date)} tarihinde, ")

        if max_expiry_date:
            lines.append(f"olağanüstü zamanaşımı süresinin ise {format_date(max_expiry_date)} tarihinde dolacağı, ")
        else:
            max_years, max_months, max_days = max_period
            max_expiry_calculated = add_period_to_date_legal(
                case_data.suc_tarihi,
                max_years,
                max_months,
                max_days,
            )
            if total_suspension_years or total_suspension_months or total_suspension_days:
                max_expiry_calculated = add_period_to_date_legal(
                    max_expiry_calculated,
                    total_suspension_years,
                    total_suspension_months,
                    total_suspension_days,
                )
            lines.append(f"olağanüstü zamanaşımı süresinin ise {format_date(max_expiry_calculated)} tarihinde dolacağı, ")

        lines.append(f"böylece zamanaşımı süresinin karar tarihinden önce {format_date(final_expiry_date)} tarihinde dolduğu anlaşılmakla; ")
        lines.append(f"5237 sayılı TCK'nın {tck_madde}. maddesi ile 5271 sayılı CMK'nın 223/8. maddesi uyarınca kamu davasının düşmesine karar verilmiştir.\n\n")

        lines.append("\tHÜKÜM:\n\n")
        lines.append(f'\t1)Her ne kadar {subject} hakkında "……" suçunu işlediği iddiasıyla kamu davası açılmış ise de; ')
        lines.append(f"zamanaşımı süresinin {format_date(final_expiry_date)} tarihinde gerçekleştiği anlaşılmakla; ")
        lines.append(f"5237 sayılı TCK'nın {tck_madde}. maddesi ile ")
        lines.append("5271 sayılı CMK'nın 223/8. maddesi uyarınca KAMU DAVASININ DÜŞMESİNE,\n")
        lines.append("\t2)Yargılama giderlerinin Hazine üzerinde bırakılmasına,\n")
        lines.append(
            "\tGerekçeli kararın tebliğden itibaren 2 hafta içerisinde, mahkememiz kalemine müracaatla zabıt kâtibine beyanla düzenlenecek tutanak veya dilekçe ile "
            "cezaevinde bulananlar yönünden aynı süre içerisinde tutuklu bulunduğu ceza infaz kurumu ve tutukevi müdürüne beyanda bulunmak suretiyle veya bu hususta "
            f"bir dilekçe vererek ........ Bölge Adliye Mahkemesi'ne istinâf başvurusunda bulunabileceğine ilişkin Cumhuriyet Savcısı huzurunda mütalaaya uygun olarak verilen karar açıkça okunup anlatıldı.{bugun}\n\n"
        )

        return "".join(lines)

from datetime import date, datetime, timedelta
from fractions import Fraction
from PyQt5.QtCore import QDate

def format_date(date_obj):
    """Format a date object as DD.MM.YYYY"""
    if isinstance(date_obj, date):
        return date_obj.strftime("%d.%m.%Y")
    return str(date_obj)

def format_number(number):
    """Format a number with thousands separator"""
    return "{:,}".format(number).replace(",", ".")

def date_diff_days(start_date, end_date):
    """Calculate the difference between two dates in days"""
    if isinstance(start_date, date) and isinstance(end_date, date):
        return (end_date - start_date).days
    return 0

def date_to_qdate(date_obj):
    """Convert a Python date to QDate"""
    if isinstance(date_obj, date):
        return QDate(date_obj.year, date_obj.month, date_obj.day)
    return QDate.currentDate()

def qdate_to_date(qdate):
    """Convert a QDate to Python date"""
    return date(qdate.year(), qdate.month(), qdate.day())

def parse_date(date_string, format_str="%d.%m.%Y"):
    """Parse a date string to date object"""
    try:
        return datetime.strptime(date_string, format_str).date()
    except ValueError:
        return None

def add_period_to_date_legal(start_date, years, months, days):
    """
    Tarihe süre ekler (HUKUK MANTIĞINA UYGUN - 30 GÜNLÜK AY)

    KRİTİK KURALLAR:
    1. Her ay mutlaka 30 gündür
    2. Ay → yıl dönüşümü YASAKTIR
    3. Gün eklenirken 30'u aşarsa fazlası aya dönüştürülür

    Args:
        start_date: Başlangıç tarihi
        years: Eklenecek yıl sayısı (tam sayı)
        months: Eklenecek ay sayısı (tam sayı)
        days: Eklenecek gün sayısı (tam sayı)

    Returns:
        Sonuç tarihi
    """
    if not isinstance(start_date, date):
        return start_date

    result_day = start_date.day + days
    result_month = start_date.month + months
    result_year = start_date.year + years

    if result_day > 30:
        extra_months = (result_day - 1) // 30
        result_month += extra_months
        result_day = ((result_day - 1) % 30) + 1

    if result_month > 12:
        extra_years = (result_month - 1) // 12
        result_year += extra_years
        result_month = ((result_month - 1) % 12) + 1

    if result_month == 2:
        is_leap = (result_year % 4 == 0 and (result_year % 100 != 0 or result_year % 400 == 0))
        max_day = 29 if is_leap else 28
    elif result_month in [4, 6, 9, 11]:
        max_day = 30
    else:
        max_day = 31

    if result_day > max_day:
        result_day = max_day

    return date(result_year, result_month, result_day)

def calculate_period_difference(start_date, end_date):
    """
    İki tarih arasındaki farkı yıl, ay ve gün olarak hesaplar
    HUKUK MANTIĞINA UYGUN: HER AY 30 GÜN KABUL EDİLİR

    Args:
        start_date: Başlangıç tarihi
        end_date: Bitiş tarihi

    Returns:
        (yıl, ay, gün) tuple'ı
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return (0, 0, 0)

    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day

    if days < 0:
        months -= 1
        days += 30

    if months < 0:
        years -= 1
        months += 12

    return (years, months, days)

def multiply_period(years, months, days, multiplier):
    """
    Bir süreyi (yıl, ay, gün) katsayı ile çarpar
    HUKUK MANTIĞINA UYGUN: Ay → yıl dönüşümü YASAKTIR

    KRİTİK KURALLAR:
    1. Yıl ayrı, ay ayrı çarpılır
    2. Gün sayısı 30'u geçerse aya çevrilir
    3. Ay sayısı 12'yi geçse bile yıla ÇEVRİLMEZ

    Args:
        years: Yıl sayısı
        months: Ay sayısı
        days: Gün sayısı
        multiplier: Çarpan (örn: 1.5, 2/3)

    Returns:
        (yıl, ay, gün) tuple'ı
    """
    mult = Fraction(multiplier).limit_denominator()

    total_years = Fraction(years) * mult
    result_years = int(total_years)
    year_fraction = total_years - result_years
    extra_months_from_years = year_fraction * 12

    total_months = Fraction(months) * mult + extra_months_from_years
    result_months = int(total_months)
    month_fraction = total_months - result_months
    extra_days_from_months = month_fraction * 30

    total_days = Fraction(days) * mult + extra_days_from_months
    result_days = int(total_days)

    if result_days >= 30:
        extra_months = result_days // 30
        result_months += extra_months
        result_days = result_days % 30

    return (result_years, result_months, result_days)

def apply_age_reduction(years, months, days, age_group):
    """
    Yaş grubuna göre süre indirimini uygular
    HUKUK MANTIĞINA UYGUN: Ay → yıl dönüşümü YASAKTIR

    Args:
        years: Yıl sayısı
        months: Ay sayısı
        days: Gün sayısı
        age_group: "12-15" veya "15-18" veya "18+"

    Returns:
        (yıl, ay, gün) tuple'ı
    """
    if age_group == "12-15":
        return multiply_period(years, months, days, 0.5)
    elif age_group == "15-18":
        return multiply_period(years, months, days, 2/3)
    else:
        return (years, months, days)

def format_period(years, months, days):
    """
    Süreyi okunabilir formatta gösterir
    Ay sayısı 12'yi geçse bile yıla ÇEVRİLMEZ

    Args:
        years: Yıl sayısı
        months: Ay sayısı (12'yi geçebilir)
        days: Gün sayısı

    Returns:
        Formatlanmış string
    """
    parts = []

    if years > 0:
        parts.append(f"{years} yıl")

    if months > 0:
        parts.append(f"{months} ay")

    if days > 0:
        parts.append(f"{days} gün")

    if not parts:
        return "0 gün"

    return " ".join(parts)

def format_period_tuple(period_tuple):
    """
    (yıl, ay, gün) tuple'ını okunabilir formatta gösterir

    Args:
        period_tuple: (yıl, ay, gün) tuple'ı

    Returns:
        Formatlanmış string
    """
    years, months, days = period_tuple
    return format_period(years, months, days)

def calculate_total_suspension_days(suspension_dates):
    """
    Calculate the total number of days from multiple suspension periods

    Args:
        suspension_dates: List of tuples (start_date, end_date)

    Returns:
        Total number of days suspended
    """
    if not suspension_dates:
        return 0

    total_days = 0
    for start_date, end_date in suspension_dates:
        total_days += date_diff_days(start_date, end_date)

    return total_days

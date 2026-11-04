"""Receiver-local PiconHub/GSU style date and split clock formatting."""
import datetime
import unittest

from WarderRadio.header_clock import _NAMES, clock_text
from WarderRadio.i18n import SUPPORTED


class RadioHeaderClockTests(unittest.TestCase):
    def test_november_receiver_screenshot_in_slovak_and_czech(self):
        moment = datetime.datetime(2026, 11, 4, 17, 10, 7)
        self.assertEqual(clock_text(moment, 'sk_SK'),
                         ('Streda', '4. novembra 2026', '17:10', ':07'))
        self.assertEqual(clock_text(moment, 'cs_CZ'),
                         ('Středa', '4. listopadu 2026', '17:10', ':07'))
        self.assertEqual(clock_text(moment, 'en_GB'),
                         ('Wednesday', '4. November 2026', '17:10', ':07'))

    def test_receiver_languages_format_without_babel_or_host_locale(self):
        moment = datetime.datetime(2026, 11, 4, 17, 10, 7)
        self.assertEqual(set(_NAMES), set(SUPPORTED))
        for code in SUPPORTED:
            with self.subTest(code=code):
                days, months = _NAMES[code]
                self.assertEqual((len(days), len(months)), (7, 12))
                day, date, hours, secs = clock_text(moment, code)
                self.assertEqual(day, days[2])
                self.assertIn('2026', date)
                self.assertTrue(months[10] in date or code == 'zh')
                self.assertEqual((hours, secs), ('17:10', ':07'))

    def test_date_conventions_keep_system_language(self):
        moment = datetime.datetime(2026, 11, 4, 17, 10, 7)
        self.assertEqual(clock_text(moment, 'hu')[1], '2026. november 4.')
        self.assertEqual(clock_text(moment, 'es')[1], '4 de noviembre de 2026')
        self.assertEqual(clock_text(moment, 'zh_CN')[1], '2026年11月4日')
        self.assertEqual(clock_text(moment, 'sq_AL')[0], 'E mërkurë')
        self.assertEqual(clock_text(moment, 'ru')[1], '4 ноября 2026')

    def test_clock_rollover(self):
        self.assertEqual(clock_text(datetime.datetime(2026, 11, 4, 23, 59, 59), 'sk')[2:],
                         ('23:59', ':59'))
        self.assertEqual(clock_text(datetime.datetime(2026, 11, 5, 0, 0, 0), 'sk')[2:],
                         ('00:00', ':00'))


if __name__ == '__main__':
    unittest.main()

import unittest

from bili_planner import UnsupportedInput, aggregate, extract_bili_links, hms, parse_target


class TestParseTarget(unittest.TestCase):
    def test_bare_bvid(self):
        self.assertEqual(parse_target('BV1BMgj6MEz4'),
                         {'kind': 'video', 'bvid': 'BV1BMgj6MEz4', 'page': None})

    def test_bare_bvid_with_spaces_and_lowercase_prefix(self):
        self.assertEqual(parse_target('  bv1BMgj6MEz4 '),
                         {'kind': 'video', 'bvid': 'BV1BMgj6MEz4', 'page': None})

    def test_video_url_with_page(self):
        t = parse_target('https://www.bilibili.com/video/BV1BMgj6MEz4/?p=3&spm_id_from=333.1007')
        self.assertEqual(t['kind'], 'video')
        self.assertEqual(t['bvid'], 'BV1BMgj6MEz4')
        self.assertEqual(t['page'], 3)

    def test_av_number(self):
        self.assertEqual(parse_target('av170001'), {'kind': 'video', 'aid': 170001, 'page': None})

    def test_av_url(self):
        t = parse_target('https://www.bilibili.com/video/av170001/?p=2')
        self.assertEqual(t['aid'], 170001)
        self.assertEqual(t['page'], 2)

    def test_series_lists_url(self):
        t = parse_target('https://space.bilibili.com/431073645/lists/4495895?type=series')
        self.assertEqual(t, {'kind': 'series', 'mid': 431073645, 'oid': 4495895})

    def test_season_lists_url(self):
        t = parse_target('https://space.bilibili.com/431073645/lists/3533058?type=season')
        self.assertEqual(t, {'kind': 'season', 'mid': 431073645, 'oid': 3533058})

    def test_collection_detail_url(self):
        t = parse_target('https://space.bilibili.com/431073645/channel/collectiondetail?sid=3533058')
        self.assertEqual(t, {'kind': 'season', 'mid': 431073645, 'oid': 3533058})

    def test_bvid_inside_query_string(self):
        t = parse_target('https://www.bilibili.com/festival/2025?bvid=BV1BMgj6MEz4')
        self.assertEqual(t['bvid'], 'BV1BMgj6MEz4')

    def test_unsupported_space_url(self):
        with self.assertRaises(UnsupportedInput):
            parse_target('https://space.bilibili.com/431073645/upload/video')

    def test_garbage(self):
        with self.assertRaises(UnsupportedInput):
            parse_target('hello world')


class TestHms(unittest.TestCase):
    def test_values(self):
        self.assertEqual(hms(43), '0:00:43')
        self.assertEqual(hms(3685), '1:01:25')
        self.assertEqual(hms(51075), '14:11:15')
        self.assertEqual(hms(0), '0:00:00')
        self.assertEqual(hms(59.6), '0:01:00')


class TestAggregate(unittest.TestCase):
    def test_totals(self):
        videos = [
            {'bvid': 'BV1', 'parts': [{'duration': 100}, {'duration': 200}]},
            {'bvid': 'BV2', 'parts': [{'duration': 50}]},
            {'bvid': 'BV3', 'parts': []},
        ]
        agg = aggregate(videos)
        self.assertEqual(agg['parts_total'], 3)
        self.assertEqual(agg['duration_total'], 350)
        self.assertEqual(agg['videos_with_parts'], 2)
        self.assertEqual(agg['videos_pending'], 1)

class TestExtractLinks(unittest.TestCase):
    def test_bv_in_url_and_plain_text(self):
        links = extract_bili_links(
            '参考 https://www.bilibili.com/video/BV1BMgj6MEz4/?p=2 ，另一个 BV1L8xH6pEhr 也看')
        self.assertEqual([l['bvid'] for l in links], ['BV1BMgj6MEz4', 'BV1L8xH6pEhr'])
        self.assertEqual(links[0]['url'], 'https://www.bilibili.com/video/BV1BMgj6MEz4')

    def test_dedup_and_order(self):
        links = extract_bili_links('BV1BMgj6MEz4 BV1BMgj6MEz4 av170001 BV1L8xH6pEhr')
        self.assertEqual([l['label'] for l in links], ['BV1BMgj6MEz4', 'av170001', 'BV1L8xH6pEhr'])

    def test_exclude_self(self):
        links = extract_bili_links('本视频 BV1BMgj6MEz4 下一集 BV1L8xH6pEhr',
                                   exclude='BV1BMgj6MEz4')
        self.assertEqual([l['bvid'] for l in links], ['BV1L8xH6pEhr'])

    def test_series_and_season_links(self):
        links = extract_bili_links(
            '系列 https://space.bilibili.com/431073645/lists/4495895?type=series ，'
            '合集 https://space.bilibili.com/431073645/channel/collectiondetail?sid=261059')
        kinds = [l['kind'] for l in links]
        self.assertEqual(kinds, ['series', 'season'])
        self.assertEqual(links[0]['oid'], 4495895)
        self.assertEqual(links[1]['oid'], 261059)

    def test_short_link(self):
        links = extract_bili_links('https://b23.tv/aB3xY9z')
        self.assertEqual(links[0]['kind'], 'short')
        self.assertEqual(links[0]['url'], 'https://b23.tv/aB3xY9z')

    def test_multiple_texts_and_empty(self):
        links = extract_bili_links('', None, 'BV1BMgj6MEz4', 'BV1L8xH6pEhr')
        self.assertEqual(len(links), 2)
        self.assertEqual(extract_bili_links(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)

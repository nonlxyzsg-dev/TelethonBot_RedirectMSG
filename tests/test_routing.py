"""Тесты маршрутизации по темам и парсинга хэштегов."""

from __future__ import annotations

from bot.routing import (
    GENERAL_TOPIC_ID,
    TopicRule,
    collect_hashtags,
    extract_hashtags,
    matching_topics,
    parse_topic_rules,
    reply_to_for_topic,
)


class TestExtractHashtags:
    def test_empty(self):
        assert extract_hashtags(None) == set()
        assert extract_hashtags("") == set()
        assert extract_hashtags("обычный текст без тегов") == set()

    def test_single_latin(self):
        assert extract_hashtags("текст #Indiana_jones конец") == {"#indiana_jones"}

    def test_multiple(self):
        text = "пост #iron_arny с тегом #трейд и #Forrest_Gump_RU"
        assert extract_hashtags(text) == {
            "#iron_arny",
            "#трейд",
            "#forrest_gump_ru",
        }

    def test_case_insensitive(self):
        """Регистр игнорируется: #Трейд == #трейд."""
        assert extract_hashtags("#Трейд") == extract_hashtags("#трейд")
        assert extract_hashtags("#Трейд") == {"#трейд"}

    def test_cyrillic(self):
        assert extract_hashtags("#трейд #новости") == {"#трейд", "#новости"}

    def test_no_word_boundary_chars(self):
        """Хэштег обрывается на пробеле/знаке препинания."""
        assert extract_hashtags("#tag.") == {"#tag"}
        assert extract_hashtags("#tag,") == {"#tag"}


class TestTopicRuleMatching:
    def test_empty_include_and_exclude_matches_everything(self):
        """Тема 1 (General): пустые include и exclude — пропускает всё."""
        rule = TopicRule(topic_id=1)
        assert rule.matches(set()) is True
        assert rule.matches({"#anything"}) is True
        assert rule.matches({"#трейд", "#x"}) is True

    def test_include_or_matches_at_least_one(self):
        """Тема 9233: include or:[#Indiana_jones]."""
        rule = TopicRule(topic_id=9233, include_or=("#Indiana_jones",))
        assert rule.matches({"#indiana_jones"}) is True
        assert rule.matches({"#indiana_jones", "#трейд"}) is True
        assert rule.matches({"#трейд"}) is False
        assert rule.matches(set()) is False

    def test_include_and_requires_all(self):
        """Тема 9211: include and:[#Indiana_jones, #трейд]."""
        rule = TopicRule(
            topic_id=9211, include_and=("#Indiana_jones", "#трейд")
        )
        assert rule.matches({"#indiana_jones", "#трейд"}) is True
        assert rule.matches({"#indiana_jones", "#трейд", "#extra"}) is True
        assert rule.matches({"#indiana_jones"}) is False
        assert rule.matches({"#трейд"}) is False
        assert rule.matches(set()) is False

    def test_exclude_or_filters_out(self):
        """Тема 9278: exclude or:[#трейд] — режет всё с #трейд."""
        rule = TopicRule(topic_id=9278, exclude_or=("#трейд",))
        assert rule.matches(set()) is True
        assert rule.matches({"#news"}) is True
        assert rule.matches({"#трейд"}) is False
        assert rule.matches({"#news", "#трейд"}) is False

    def test_exclude_and_only_filters_when_all_present(self):
        rule = TopicRule(topic_id=42, exclude_and=("#a", "#b"))
        assert rule.matches({"#a"}) is True
        assert rule.matches({"#b"}) is True
        assert rule.matches({"#a", "#b"}) is False

    def test_include_or_with_exclude_or(self):
        rule = TopicRule(
            topic_id=99, include_or=("#main",), exclude_or=("#nsfw",)
        )
        assert rule.matches({"#main"}) is True
        assert rule.matches({"#main", "#other"}) is True
        assert rule.matches({"#main", "#nsfw"}) is False
        assert rule.matches({"#nsfw"}) is False
        assert rule.matches(set()) is False

    def test_case_insensitive(self):
        rule = TopicRule(topic_id=1, include_or=("#TAG",))
        assert rule.matches({"#tag"}) is True


class TestMatchingTopicsRealConfig:
    """Кейсы из реального конфига пользователя."""

    @staticmethod
    def _rules():
        raw = {
            "1": {"include": {"or": []}, "exclude": {"or": []}},
            "9233": {"include": {"or": ["#Indiana_jones"]}, "exclude": {"or": []}},
            "9211": {
                "include": {"and": ["#Indiana_jones", "#трейд"]},
                "exclude": {"or": []},
            },
            "9237": {"include": {"or": ["#iron_arny"]}, "exclude": {"or": []}},
            "9235": {
                "include": {"and": ["#iron_arny", "#трейд"]},
                "exclude": {"or": []},
            },
            "9241": {"include": {"or": ["#Forrest_Gump_RU"]}, "exclude": {"or": []}},
            "9239": {
                "include": {"and": ["#Forrest_Gump_RU", "#трейд"]},
                "exclude": {"or": []},
            },
            "9278": {"include": {"or": []}, "exclude": {"or": ["#трейд"]}},
        }
        return parse_topic_rules(raw)

    def test_indiana_with_trade_lands_in_three_topics(self):
        """#Indiana_jones #трейд → 1 (General), 9233 (or), 9211 (and)."""
        tags = {"#indiana_jones", "#трейд"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9233, 9211}

    def test_indiana_only_lands_in_two(self):
        """#Indiana_jones (без #трейд) → 1, 9233, 9278."""
        tags = {"#indiana_jones"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9233, 9278}

    def test_iron_arny_with_trade(self):
        tags = {"#iron_arny", "#трейд"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9237, 9235}

    def test_no_hashtags_goes_to_general_and_non_trade(self):
        """Сообщение без хэштегов: General + 9278 (нет #трейд)."""
        tags: set[str] = set()
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9278}

    def test_only_trade_no_category(self):
        """#трейд без категории: только General (9278 отсекает по exclude)."""
        tags = {"#трейд"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1}

    def test_unknown_hashtag(self):
        """Неизвестный тег: General + 9278 (как и без тегов вообще)."""
        tags = {"#some_other"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9278}

    def test_case_does_not_matter(self):
        """#ИНДИАНА_JONES должен матчиться так же, как #indiana_jones."""
        tags = extract_hashtags("текст с #INDIANA_JONES")
        assert tags == {"#indiana_jones"}
        topics = set(matching_topics(tags, self._rules()))
        assert topics == {1, 9233, 9278}


class TestParseTopicRules:
    def test_empty_dict(self):
        assert parse_topic_rules({}) == []
        assert parse_topic_rules(None) == []

    def test_skips_non_numeric_keys(self):
        raw = {"abc": {"include": {"or": []}}, "42": {"include": {"or": []}}}
        rules = parse_topic_rules(raw)
        assert [r.topic_id for r in rules] == [42]

    def test_handles_missing_sections(self):
        rules = parse_topic_rules({"1": {}})
        assert rules[0].include_or == ()
        assert rules[0].exclude_or == ()


class TestCollectHashtagsFromMessages:
    class _Msg:
        def __init__(self, text=None, message=None):
            self.text = text
            self.message = message

    def test_combines_text_and_message(self):
        m1 = self._Msg(text="#indiana_jones первое")
        m2 = self._Msg(message="#трейд второе")
        assert collect_hashtags([m1, m2]) == {"#indiana_jones", "#трейд"}

    def test_album_caption_picked_up(self):
        """Альбом: caption обычно лежит в одном из сообщений группы."""
        empty = self._Msg(text=None)
        with_caption = self._Msg(text="фото #Forrest_Gump_RU #трейд")
        assert collect_hashtags([empty, empty, with_caption]) == {
            "#forrest_gump_ru",
            "#трейд",
        }


class TestReplyToForTopic:
    def test_general_returns_none(self):
        assert reply_to_for_topic(GENERAL_TOPIC_ID) is None
        assert reply_to_for_topic(1) is None

    def test_other_returns_topic_id(self):
        assert reply_to_for_topic(9233) == 9233

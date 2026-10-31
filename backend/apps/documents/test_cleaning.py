from apps.documents.cleaning import clean_text, remove_boilerplate


def test_fixes_ligatures_and_removes_control_characters():
    assert clean_text("ﬁnance\x00 report") == "finance report"


def test_fixes_hyphenated_line_breaks():
    assert clean_text("inter-\nnational trade") == "international trade"


def test_joins_wrapped_lines_but_keeps_paragraphs():
    text = "This is a long\nsentence.\n\nSecond paragraph."
    assert clean_text(text) == "This is a long sentence.\n\nSecond paragraph."


def test_keeps_bullet_items_on_separate_lines():
    assert clean_text("Items:\n- apples\n- pears") == "Items:\n- apples\n- pears"


def test_collapses_extra_spaces_and_blank_lines():
    assert clean_text("a   b\n\n\n\nc") == "a b\n\nc"


def test_empty_text_stays_empty():
    assert clean_text("   \n  ") == ""


def test_removes_repeated_headers_and_page_numbers():
    pages = [
        "ACME CONFIDENTIAL\nIntro text one\nPage 1",
        "ACME CONFIDENTIAL\nSecond page text\nPage 2",
        "ACME CONFIDENTIAL\nThird page text\nPage 3",
    ]

    result = remove_boilerplate(pages)

    assert [page.strip() for page in result] == [
        "Intro text one",
        "Second page text",
        "Third page text",
    ]


def test_header_removal_needs_enough_pages():
    pages = ["ACME CONFIDENTIAL\nOne text", "ACME CONFIDENTIAL\nTwo text"]

    result = remove_boilerplate(pages)

    assert all("ACME CONFIDENTIAL" in page for page in result)


def test_numbers_in_the_middle_of_a_page_are_kept():
    result = remove_boilerplate(["a\nb\n42\nc\nd"])

    assert "42" in result[0]

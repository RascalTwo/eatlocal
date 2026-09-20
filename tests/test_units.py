"""eatlocal unit tests"""

import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest

from eatlocal.eatlocal import (
    Bite,
    all_bites,
    fetch_bites,
    choose_bite,
    choose_local_bite,
    create_bite_dir,
    display_bite,
    extract_test_report,
    fetch_template_code,
    is_test_writing_bite,
    get_credentials,
    load_config,
    set_local_dir,
    _unformat_bite_key,
    _format_bite_key,
)

NOT_DOWNLOADED = (
    Bite(
        "Made up bite",
        "made-up-bite",
    ),
    Bite("Write a property", "write-a-property"),
)
LOCAL_TEST_BITE = Bite(
    "Parse a list of names",
    "parse-a-list-of-names",
)
SUMMING_TEST_BITE = Bite(
    "Sum n numbers",
    "sum-n-numbers",
)


def test_bite_implementation():
    """Test Bite class implementation."""
    bite = SUMMING_TEST_BITE
    assert bite.title == "Sum n numbers"
    assert bite.slug == "sum-n-numbers"
    assert bite.url == "https://pybitesplatform.com/bites/sum-n-numbers/"
    assert bite.platform_content is None


def test_bite_fetch_local_code(testing_config) -> None:
    """Test fetching local code."""
    bite = LOCAL_TEST_BITE
    bite_dir = Path(testing_config["PYBITES_REPO"]) / LOCAL_TEST_BITE.slug
    with open(bite_dir / "names.py", "r") as f:
        local_code = f.read()
    bite.fetch_local_code(testing_config)
    assert bite.local_code == local_code


def test_bite_fetch_local_code_no_file(capsys, testing_config) -> None:
    """Test fetching local code when file does not exist."""
    bite = NOT_DOWNLOADED[0]
    bite.fetch_local_code(testing_config)
    output = capsys.readouterr()
    assert "Unable to find bite" in output.out


@patch("eatlocal.eatlocal.iterfzf")
def test_choose_local_bite(mock_iterfzf, testing_config) -> None:
    """Test choosing a local bite."""
    mock_iterfzf.return_value = LOCAL_TEST_BITE.title
    with patch(
        "eatlocal.eatlocal.LOCAL_BITES_DB",
        Path.cwd() / "tests/testing_repo/.local_bites.json",
    ):
        bite = choose_local_bite(testing_config)
    assert bite.title == LOCAL_TEST_BITE.title
    assert bite.slug == LOCAL_TEST_BITE.slug


@pytest.fixture
def test_choose_local_bite_from_dir(monkeypatch, testing_config) -> None:
    """Test choosing a local bite."""
    with patch(
        "eatlocal.eatlocal.LOCAL_BITES_DB",
        Path.cwd() / "tests/testing_repo/.local_bites.json",
    ):
        monkeypatch.chdir("tests/testing_repo/parse-a-list-of-names/")
        bite = choose_local_bite(testing_config)
    assert bite.title == LOCAL_TEST_BITE.title
    assert bite.slug == LOCAL_TEST_BITE.slug


@patch("eatlocal.eatlocal.Prompt.ask")
@patch("eatlocal.eatlocal.Path.exists")
def test_set_local_dir(mock_exists, mock_prompt):
    mock_prompt.return_value = "/some/path"
    mock_exists.return_value = True
    local_dir = set_local_dir()
    assert local_dir == Path("/some/path")


@patch("eatlocal.eatlocal.requests.get")
@patch("eatlocal.eatlocal.iterfzf")
def test_choose_bite(mock_iterfzf, mock_requests):
    mock_response = MagicMock()
    mock_response.status_code = 200
    api_data = json.load(open("./tests/testing_content/bites_api.json"))
    mock_response.json.return_value = api_data
    mock_requests.return_value = mock_response

    # Create the formatted title that would be displayed in iterfzf
    max_title_length = max(len(bite["title"]) for bite in api_data)
    padding = max_title_length + 10
    formatted_title = _format_bite_key(
        SUMMING_TEST_BITE.title,
        next(
            bite["level"]
            for bite in api_data
            if bite["title"] == SUMMING_TEST_BITE.title
        ),
        padding,
    )

    # Mock iterfzf to return the formatted title
    mock_iterfzf.return_value = formatted_title

    bite = choose_bite()
    assert isinstance(bite, Bite)
    # We need to unformat the title to match it with the original
    assert _unformat_bite_key(bite.title) == SUMMING_TEST_BITE.title
    assert bite.slug == SUMMING_TEST_BITE.slug


def test_display_bite(
    testing_config,
    capsys,
) -> None:
    """Correctly display a bite that has been downloaded and extracted."""
    display_bite(LOCAL_TEST_BITE, testing_config, theme="material")
    output = capsys.readouterr().out
    assert f"Displaying {LOCAL_TEST_BITE.title} at" in output
    assert "Code" in output
    assert "Directions" in output


@pytest.mark.parametrize("bite", NOT_DOWNLOADED)
def test_cannot_display_missing_bite(
    bite,
    testing_config,
    capsys,
) -> None:
    """Attempt to display a bite that has not been downloaded and extracted."""

    display_bite(bite, testing_config, theme="material")
    output = capsys.readouterr().out
    assert "Unable to display bite" in output


def test_create_bite_dir(
    testing_config,
) -> None:
    """Create a directory for a bite."""
    with open(Path("./tests/testing_content/summing_content.txt"), "r") as f:
        platform_content = f.read()
    bite = SUMMING_TEST_BITE
    bite.platform_content = platform_content
    bite_dir = Path(testing_config["PYBITES_REPO"]) / "sum-n-numbers"

    create_bite_dir(bite, testing_config)
    html_file = bite_dir / "bite.html"
    python_file = bite_dir / "summing.py"
    test_file = bite_dir / "test_summing.py"
    assert html_file.exists()
    assert python_file.exists()
    assert test_file.exists()
    assert bite_dir.is_dir()
    assert bite_dir.name == "sum-n-numbers"
    shutil.rmtree(bite_dir)


def test_create_bite_dir_keeps_whole_filename(
    testing_config,
) -> None:
    """The module name is a suffix to strip, not a set of characters.

    `str.strip(".py")` ate any leading/trailing `.`, `p` or `y`, so a Bite whose
    module is `app` landed on disk as `a.py` and the tests could not import it.
    """
    with open(Path("./tests/testing_content/fastapi_content.txt"), "r") as f:
        platform_content = f.read()
    bite = Bite("Fastapi hello world", "fastapi-hello-world")
    bite.platform_content = platform_content
    bite_dir = Path(testing_config["PYBITES_REPO"]) / "fastapi-hello-world"

    try:
        create_bite_dir(bite, testing_config)

        assert (bite_dir / "app.py").exists()
        assert (bite_dir / "test_app.py").exists()
        assert not (bite_dir / "a.py").exists()
    finally:
        shutil.rmtree(bite_dir, ignore_errors=True)


def test_create_bite_dir_without_force(testing_config, capsys):
    create_bite_dir(LOCAL_TEST_BITE, testing_config)
    output = capsys.readouterr().out
    assert "There already exists a directory for" in output
    assert "Use the --force option" in output


def test_load_config() -> None:
    """Load the configuration file."""
    expected = {
        "PYBITES_USERNAME": "test_username",
        "PYBITES_PASSWORD": "test_password",
        "PYBITES_REPO": "test_repo",
    }
    actual = load_config(Path("./tests/testing_content/testing_env").resolve())
    assert actual == expected


def test_load_config_file_not_found(capsys) -> None:
    """Test loading a config file that does not exist."""
    with pytest.raises(SystemExit):
        load_config(Path("./tests/testing_content/non_existent_file").resolve())
    output = capsys.readouterr().out
    assert "Could not find or read .eatlocal/.env in your home directory." in output


@patch("eatlocal.eatlocal.Prompt.ask")
def test_get_credentials(mock_prompt) -> None:
    """Test getting credentials from the config file."""
    expected = ("test_username", "test_password")
    mock_prompt.side_effect = ["test_username", "test_password", "test_password"]
    actual = get_credentials()
    assert actual == expected


PASSING_FEEDBACK = """
                Congrats, you passed this Bite earning 2 points 🎉
                ========== test session starts ==========
                collected 2 items
                test_summing.py ..                              [100%]
                ========== 2 passed in 0.02s ==========

                View SolutionPython Beginner1/20Next →
"""

FAILING_FEEDBACK = """
                ========== test session starts ==========
                collected 2 items
                test_summing.py F.                              [ 50%]
                ============== FAILURES ==============
                E       assert None == 5050
                ========== 1 failed, 1 passed in 0.03s ==========

                View SolutionNext →
"""


def test_extract_test_report_keeps_the_failure() -> None:
    """A failed submit should say what pytest actually complained about."""
    report = extract_test_report(FAILING_FEEDBACK)
    assert report.startswith("========== test session starts")
    assert "assert None == 5050" in report
    assert "1 failed, 1 passed" in report
    assert "View Solution" not in report


def test_extract_test_report_drops_the_verdict_line() -> None:
    """The Congrats banner is already printed by the caller."""
    report = extract_test_report(PASSING_FEEDBACK)
    assert "Congrats" not in report
    assert report.startswith("========== test session starts")


def test_extract_test_report_falls_back_to_whole_panel() -> None:
    """If pytest never ran, show whatever the platform did say."""
    assert extract_test_report("  Server error, try again  ") == "Server error, try again"



def test_fetch_template_code_uses_the_reset_dropdown() -> None:
    """Reset goes through the platform's own control, not a hand-built URL.

    Selecting it also lets the page clear the draft it caches in localStorage.
    """
    page = MagicMock()
    response = MagicMock(ok=True)
    response.json.return_value = {
        "code": "def sum_numbers(numbers=None):\r\n    pass",
        "reset": True,
    }
    page.expect_response.return_value.__enter__.return_value.value = response

    code = fetch_template_code(page, SUMMING_TEST_BITE)

    page.select_option.assert_called_once_with("#submissions", "reset")
    assert code == "def sum_numbers(numbers=None):\r\n    pass"


def test_fetch_template_code_without_a_reset_control(capsys) -> None:
    """No dropdown means nothing to reset; say so and keep what we have."""
    page = MagicMock()
    page.query_selector.return_value = None

    assert fetch_template_code(page, SUMMING_TEST_BITE) is None
    page.select_option.assert_not_called()
    assert "No reset control" in capsys.readouterr().out


def test_fetch_template_code_survives_a_bad_response(capsys) -> None:
    """A platform hiccup should not lose the code we already have."""
    page = MagicMock()
    page.expect_response.return_value.__enter__.return_value.value = MagicMock(ok=False)

    assert fetch_template_code(page, SUMMING_TEST_BITE) is None
    assert "Unable to reset" in capsys.readouterr().out



def test_create_bite_dir_prefers_the_template(testing_config) -> None:
    """With --reset the template wins over the submission in the editor."""
    with open(Path("./tests/testing_content/fastapi_content.txt"), "r") as f:
        platform_content = f.read()
    bite = Bite("Fastapi hello world", "fastapi-hello-world")
    bite.platform_content = platform_content
    bite.template_code = "# Enter your code below this line\n"
    bite_dir = Path(testing_config["PYBITES_REPO"]) / "fastapi-hello-world"

    try:
        create_bite_dir(bite, testing_config)
        written = (bite_dir / "app.py").read_text()
        assert written == "# Enter your code below this line\n"
        assert "FastAPI()" not in written
    finally:
        shutil.rmtree(bite_dir, ignore_errors=True)


@patch("eatlocal.eatlocal.requests.get")
def test_all_bites_skips_the_picker(mock_requests) -> None:
    """--all returns every Bite without prompting."""
    mock_requests.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=json.load(open("./tests/testing_content/bites_api.json"))
        ),
    )

    bites = all_bites()

    assert len(bites) == 3
    assert all(isinstance(b, Bite) for b in bites)
    assert "sum-n-numbers" in {b.slug for b in bites}


@patch("eatlocal.eatlocal.requests.get")
def test_all_bites_honours_level(mock_requests) -> None:
    """--all pairs with --level rather than replacing it."""
    mock_requests.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=json.load(open("./tests/testing_content/bites_api.json"))
        ),
    )

    bites = all_bites(level="beginner")

    assert [b.slug for b in bites] == ["sum-n-numbers"]


@patch("eatlocal.eatlocal.requests.get")
def test_fetch_bites_rejects_an_unknown_level(mock_requests, capsys) -> None:
    """A typo'd level should stop rather than silently download everything."""
    mock_requests.return_value = MagicMock(
        status_code=200, json=MagicMock(return_value=[])
    )

    with pytest.raises(SystemExit):
        fetch_bites(level="expert")
    assert "Invalid level" in capsys.readouterr().out


def test_create_bite_dir_skips_an_inaccessible_bite(testing_config, capsys) -> None:
    """A paywalled Bite must not abort a bulk download."""
    bite = Bite("Premium bite", "premium-bite")
    bite.platform_content = "<html><body>no editor here</body></html>"

    assert create_bite_dir(bite, testing_config) is False
    assert "Unable to access" in capsys.readouterr().out
    assert not (Path(testing_config["PYBITES_REPO"]) / "premium-bite").exists()


def test_create_bite_dir_reports_success(testing_config) -> None:
    """A written Bite reports True so callers can count it."""
    with open(Path("./tests/testing_content/fastapi_content.txt"), "r") as f:
        platform_content = f.read()
    bite = Bite("Fastapi hello world", "fastapi-hello-world")
    bite.platform_content = platform_content
    bite_dir = Path(testing_config["PYBITES_REPO"]) / "fastapi-hello-world"

    try:
        assert create_bite_dir(bite, testing_config) is True
    finally:
        shutil.rmtree(bite_dir, ignore_errors=True)


IMPLEMENTATION = "from functools import cache\n\n\ndef fib(n):\n    return n\n"
TEST_STUB = "from fibonacci import fib\n\n# write one or more pytest functions below\n"


def test_spots_a_write_the_tests_bite() -> None:
    """The editor imports the module; the "tests" panel is the module."""
    assert is_test_writing_bite(TEST_STUB, IMPLEMENTATION, "fibonacci")


def test_leaves_ordinary_bites_alone() -> None:
    """Normally the stub is the module and the tests import it."""
    code = "def sum_numbers(numbers=None):\n    pass\n"
    tests = "from summing import sum_numbers\n\n\ndef test_it():\n    assert True\n"
    assert not is_test_writing_bite(code, tests, "summing")


def test_detection_needs_both_signals() -> None:
    """A stub importing its own module is not enough if the tests also do."""
    code = "from summing import helper\n"
    tests = "from summing import sum_numbers\n"
    assert not is_test_writing_bite(code, tests, "summing")


def test_create_bite_dir_unswaps_a_write_the_tests_bite(testing_config) -> None:
    """The implementation must land in the module, not in the test file."""
    with open(Path("./tests/testing_content/write_tests_content.txt"), "r") as f:
        platform_content = f.read()
    bite = Bite("Write tests for fibonacci", "write-tests-for-fibonacci")
    bite.platform_content = platform_content
    bite_dir = Path(testing_config["PYBITES_REPO"]) / "write-tests-for-fibonacci"

    try:
        create_bite_dir(bite, testing_config)
        module = (bite_dir / "fibonacci.py").read_text()
        test = (bite_dir / "test_fibonacci.py").read_text()
        assert "def fib(n):" in module
        assert "from fibonacci import fib" not in module, "module imported itself"
        assert "from fibonacci import fib" in test
    finally:
        shutil.rmtree(bite_dir, ignore_errors=True)


def test_fetch_local_code_can_prefer_the_test_file(tmp_path) -> None:
    """Submitting a write-the-tests Bite sends test_<module>.py."""
    bite_dir = tmp_path / "write-tests-for-fibonacci"
    bite_dir.mkdir()
    (bite_dir / "fibonacci.py").write_text("def fib(n):\n    return n\n")
    (bite_dir / "test_fibonacci.py").write_text("def test_fib():\n    assert True\n")
    bite = Bite("Write tests for fibonacci", "write-tests-for-fibonacci")
    config = {"PYBITES_REPO": tmp_path}

    bite.fetch_local_code(config, prefer_tests=True)
    assert bite.local_code == "def test_fib():\n    assert True\n"

    bite.fetch_local_code(config)
    assert bite.local_code == "def fib(n):\n    return n\n"

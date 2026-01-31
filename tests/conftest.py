"""Pytest configuration and shared fixtures for igold scraper tests."""
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_time_sleep():
    """Automatically patch time.sleep to speed up tests."""
    with patch('time.sleep'):
        yield


@pytest.fixture
def mock_session():
    """Provide a mock session to avoid creating real Session objects."""
    mock_sess = Mock()
    mock_sess.get = Mock()
    mock_sess.close = Mock()
    return mock_sess


@pytest.fixture
def mock_scraper_session():
    """Patch requests.Session to return a mock session for all scrapers."""
    with patch('src.igold_scraper.scrapers.base.requests.Session') as mock_session_class:
        mock_sess = Mock()
        mock_sess.get = Mock()
        mock_sess.close = Mock()
        mock_sess.headers = Mock()
        mock_sess.headers.update = Mock()
        mock_sess.mount = Mock()
        mock_session_class.return_value = mock_sess
        yield mock_sess


@pytest.fixture
def sample_gold_product_coin():
    """Minimal HTML for a gold coin product - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Gold Coin</title>
    </head>
    <body>
        <main>
            <h1>31.1 гр. Златна Монета Тест Монета</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>3833.33 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>7500.00 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>3680.00 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>7200.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>31.1 гр.</strong></p>
            <p>Проба: <strong>999/1000</strong></p>
            <p>Чисто злато: <strong>31.1 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_gold_product_bar():
    """Minimal HTML for a gold bar product - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Gold Bar</title>
    </head>
    <body>
        <main>
            <h1>10 гр. Златно Кюлче Тест Производител</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>1277.95 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>2500.00 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>1226.61 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>2400.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>10 гр.</strong></p>
            <p>Проба: <strong>999.9/1000</strong></p>
            <p>Чисто злато: <strong>10 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_gold_product_html():
    """Alias for sample_gold_product_coin for backward compatibility."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Gold Product</title>
    </head>
    <body>
        <main>
            <h1>3.99 гр. Златна Монета Тест</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>486.75 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>952.00 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>466.81 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>913.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>3.99 гр.</strong></p>
            <p>Проба: <strong>916.7/1000</strong></p>
            <p>Чисто злато: <strong>3.66 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_silver_product_coin():
    """Minimal HTML for a silver coin product - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Silver Coin</title>
    </head>
    <body>
        <main>
            <h1>31.1 гр. Сребърна Монета Тест Монета</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>92.00 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>180.00 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>84.36 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>165.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>31.1 гр.</strong></p>
            <p>Проба: <strong>999/1000</strong></p>
            <p>Чисто сребро: <strong>31.1 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_silver_product_bar():
    """Minimal HTML for a silver bar product - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Silver Bar</title>
    </head>
    <body>
        <main>
            <h1>100 гр. Сребърно Кюлче Тест Производител</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>281.19 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>550.00 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>255.62 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>500.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>100 гр.</strong></p>
            <p>Проба: <strong>999.9/1000</strong></p>
            <p>Чисто сребро: <strong>100 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_silver_product_html():
    """Alias for sample_silver_product_coin for backward compatibility."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Silver Product</title>
    </head>
    <body>
        <main>
            <h1>31.1 гр. Сребърна Монета Тест</h1>
        </main>
        <regular-product>
            <table>
                <tbody>
                    <tr>
                        <td>Продаваме</td>
                        <td><span>38.62 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>75.50 лв.</span></td>
                    </tr>
                    <tr>
                        <td>&nbsp;</td>
                    </tr>
                    <tr>
                        <td>Купуваме</td>
                        <td><span>30.68 €</span></td>
                    </tr>
                    <tr>
                        <td></td>
                        <td><span>60.00 лв.</span></td>
                    </tr>
                </tbody>
            </table>
        </regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: <strong>31.1 гр.</strong></p>
            <p>Проба: <strong>999/1000</strong></p>
            <p>Чисто сребро: <strong>31.06 гр.</strong></p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_gold_category_html():
    """Minimal HTML for a gold category page - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Злато - Test</title>
    </head>
    <body>
        <ul>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-gold-coin-1">
                        <h2>31.1 гр. Златна Монета Тест 1</h2>
                    </a>
                </dd>
            </li>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-gold-bar-1">
                        <h2>10 гр. Златно Кюлче Тест 1</h2>
                    </a>
                </dd>
            </li>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-gold-coin-2">
                        <h2>3.99 гр. Златна Монета Тест 2</h2>
                    </a>
                </dd>
            </li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_silver_category_html():
    """Minimal HTML for a silver category page - matches XPath structure."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Сребро - Test</title>
    </head>
    <body>
        <ul>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-silver-coin-1">
                        <h2>31.1 гр. Сребърна Монета Тест 1</h2>
                    </a>
                </dd>
            </li>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-silver-bar-1">
                        <h2>100 гр. Сребърно Кюлче Тест 1</h2>
                    </a>
                </dd>
            </li>
            <li class="kv__member-item">
                <dd class="kv__member-name">
                    <a href="/test-silver-coin-2">
                        <h2>31.1 гр. Сребърна Монета Тест 2</h2>
                    </a>
                </dd>
            </li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_product_data():
    """Sample extracted product data for testing."""
    return {
        'product_name': 'Test Gold Coin',
        'url': 'https://igold.bg/test-product',
        'product_type': 'coin',
        'total_weight_g': 31.1,
        'purity_per_mille': 999.0,
        'fine_gold_g': 31.06,
        'sell_price_eur': 3833.33,
        'buy_price_eur': 3680.00,
        'price_per_g_fine_eur': 123.47,
        'spread_percentage': 4.0,
    }

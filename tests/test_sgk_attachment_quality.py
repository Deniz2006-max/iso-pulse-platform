import unittest
from unittest.mock import AsyncMock, patch

from src.ingestion.sgk_scraper import _detail_text, _pdf_text


class SgkAttachmentQualityTests(unittest.IsolatedAsyncioTestCase):
    async def test_pdf_extraction_requests_all_pages(self):
        client = AsyncMock()
        client.get_bytes.return_value = (b'%PDF-fixture', 'application/pdf', 200)
        with patch('src.ingestion.sgk_scraper.pdf_bytes_to_text_async',
                   new=AsyncMock(return_value='Synthetic PDF text')) as extract:
            self.assertEqual(await _pdf_text(client, 'https://example.test/a.pdf'), 'Synthetic PDF text')
            extract.assert_awaited_once_with(b'%PDF-fixture', max_pages=None)

    async def extract(self, results):
        links = ''.join(f'<a href="/Download/DownloadFile?f={i}"></a>'
                        for i in range(len(results)))
        client = AsyncMock()
        client.get_html.return_value = (
            '<div class="announcement-detail-title">Fixture title</div>'
            '<div class="document-item"><span class="speak-area">Fixture attachment</span></div>'
            + links
        )
        with patch('src.ingestion.sgk_scraper._pdf_text', new=AsyncMock(side_effect=results)):
            return await _detail_text(client, 'https://example.test/sgk/1')

    async def test_attachment_labels_are_not_publication_text(self):
        self.assertEqual(await self.extract(['']), '')

    async def test_one_missing_attachment_prevents_partial_baseline(self):
        self.assertEqual(await self.extract(['Synthetic extracted PDF', '']), '')

    async def test_successfully_extracted_attachment_is_kept(self):
        text = await self.extract(['Synthetic extracted PDF'])
        self.assertIn('Synthetic extracted PDF', text)
        self.assertIn('Fixture title', text)

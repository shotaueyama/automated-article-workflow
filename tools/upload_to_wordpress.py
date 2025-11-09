#!/usr/bin/env python3
"""Upload a markdown or HTML article (and local images) to WordPress via REST API."""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import markdown
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

IMG_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")
TITLE_PATTERN = re.compile(r"^#\s+(?P<title>.+)$", re.MULTILINE)
DEFAULT_CATEGORY = "ブログ"
DEFAULT_PARENT_CATEGORY = "QUON COLLEGE"


@dataclass
class ImageRef:
    rel_path: str
    abs_path: Path
    alt_text: str


class WordPressUploader:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        if not base_url.endswith("/"):
            base_url = base_url.rstrip("/")
        self.base_url = base_url
        self.session = requests.Session()
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
        self.session.headers.update({"Authorization": f"Basic {token}"})
        self._categories_cache: Optional[List[dict]] = None

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}wp-json/wp/v2{endpoint}"
        response = self.session.request(method, url, **kwargs)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise SystemExit(f"WordPress API error ({response.status_code}): {response.text}") from exc
        return response

    def fetch_categories(self) -> List[dict]:
        categories: List[dict] = []
        page = 1
        while True:
            resp = self._request(
                "GET",
                "/categories",
                params={"per_page": 100, "page": page},
            )
            data = resp.json()
            if not data:
                break
            categories.extend(data)
            if len(data) < 100:
                break
            page += 1
        return categories

    def resolve_category_id(self, name: str, parent_name: Optional[str]) -> int:
        categories = self._get_categories()
        by_id = {cat["id"]: cat for cat in categories}
        for cat in categories:
            if cat["name"] != name:
                continue
            if parent_name is None:
                return cat["id"]
            parent = by_id.get(cat["parent"])
            if parent and parent["name"] == parent_name:
                return cat["id"]
        raise SystemExit(f"Category '{name}' (parent: {parent_name}) not found via REST API.")

    def resolve_category_id_by_name(self, name: str) -> int:
        categories = self._get_categories()
        for cat in categories:
            if cat["name"] == name:
                return cat["id"]
        raise SystemExit(f"Category '{name}' not found via REST API.")

    def _get_categories(self) -> List[dict]:
        if self._categories_cache is None:
            self._categories_cache = self.fetch_categories()
        return self._categories_cache

    def upload_media(self, image: ImageRef) -> dict:
        mime_type, _ = mimetypes.guess_type(image.abs_path.name)
        mime_type = mime_type or "application/octet-stream"
        with image.abs_path.open("rb") as file_handle:
            files = {"file": (image.abs_path.name, file_handle, mime_type)}
            data = {
                "title": image.abs_path.stem,
                "alt_text": image.alt_text or image.abs_path.stem,
            }
            resp = self._request("POST", "/media", files=files, data=data)
        media = resp.json()
        return media

    def create_post(self, title: Optional[str], content: str, categories: List[int], status: str, featured_media_id: Optional[int] = None) -> dict:
        payload = {
            "content": content,
            "status": status,
            "categories": categories,
        }
        if title is not None:
            payload["title"] = title
        if featured_media_id is not None:
            payload["featured_media"] = featured_media_id
        resp = self._request("POST", "/posts", json=payload)
        return resp.json()


def extract_title_from_markdown(markdown_text: str) -> str:
    match = TITLE_PATTERN.search(markdown_text)
    if not match:
        raise SystemExit("No H1 title found in markdown.")
    return match.group("title").strip()


def extract_title_from_html(html_text: str) -> str:
    """HTMLから最初のh1またはh2タグからタイトルを抽出"""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # h1タグを探す
    h1_tag = soup.find("h1")
    if h1_tag:
        return h1_tag.get_text().strip()
    
    # h1がなければh2タグを探す
    h2_tag = soup.find("h2")
    if h2_tag:
        return h2_tag.get_text().strip()
    
    raise SystemExit("No H1 or H2 title found in HTML.")


def remove_h1_from_html(html_text: str) -> str:
    """HTMLコンテンツからh1タグを除去（WordPressではタイトル欄に入れるため）"""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # 最初のh1タグを探して除去
    h1_tag = soup.find("h1")
    if h1_tag:
        h1_tag.decompose()  # h1タグを完全に除去
    
    return str(soup)


def remove_leading_title(markdown_text: str) -> str:
    match = TITLE_PATTERN.search(markdown_text)
    if not match:
        return markdown_text
    _, end = match.span()
    remainder = markdown_text[end:]
    return remainder.lstrip("\r\n")


def find_local_images_from_markdown(markdown_text: str, article_path: Path) -> List[ImageRef]:
    refs: List[ImageRef] = []
    for match in IMG_PATTERN.finditer(markdown_text):
        rel = match.group("path")
        if rel.startswith("http://") or rel.startswith("https://"):
            continue
        abs_path = (article_path.parent / rel).resolve()
        if not abs_path.exists():
            raise SystemExit(f"Image path not found: {rel} -> {abs_path}")
        refs.append(ImageRef(rel_path=rel, abs_path=abs_path, alt_text=match.group("alt")))
    return refs


def find_local_images_from_html(html_text: str, article_path: Path) -> List[ImageRef]:
    """HTMLから画像参照を抽出"""
    refs: List[ImageRef] = []
    soup = BeautifulSoup(html_text, "html.parser")
    
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "")
        if not src or src.startswith("http://") or src.startswith("https://"):
            continue
        
        abs_path = (article_path.parent / src).resolve()
        if not abs_path.exists():
            raise SystemExit(f"Image path not found: {src} -> {abs_path}")
        
        alt_text = img_tag.get("alt", "")
        refs.append(ImageRef(rel_path=src, abs_path=abs_path, alt_text=alt_text))
    
    return refs


def remove_placeholder_figures(html_text: str) -> str:
    """プレースホルダー画像を含むfigureタグを除去"""
    soup = BeautifulSoup(html_text, "html.parser")
    
    # example.comやプレースホルダーURLを含むfigureタグを除去
    for figure in soup.find_all("figure"):
        img_tag = figure.find("img")
        if img_tag:
            src = img_tag.get("src", "")
            if src and ("example.com" in src or src.startswith("http")):
                print(f"Removing placeholder figure: {src}")
                figure.decompose()
    
    return str(soup)


def replace_image_urls(html_content: str, replacements: Dict[str, str]) -> str:
    updated = html_content
    for rel_path, remote_url in replacements.items():
        updated = updated.replace(rel_path, remote_url)
    return updated


def convert_html_to_blocks(html_content: str, media_info: Dict[str, dict]) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    blocks: List[str] = []
    
    # 順序を保持してすべてのブロックレベル要素を取得
    block_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img', 'ul', 'ol', 'blockquote', 'pre', 'div'])
    
    for element in block_elements:
        block = convert_node_to_block(element, media_info)
        if block:
            blocks.append(block)
    
    return "\n\n".join(blocks)


def convert_node_to_block(node: Union[Tag, NavigableString], media_info: Dict[str, dict]) -> Optional[str]:
    if isinstance(node, NavigableString):
        text = node.strip()
        if not text:
            return None
        return make_paragraph_block(html.escape(text))
    if not isinstance(node, Tag):
        return None
    if node.name == "p":
        content_nodes = [child for child in node.contents if not _is_whitespace(child)]
        if len(content_nodes) == 1 and isinstance(content_nodes[0], Tag) and content_nodes[0].name == "img":
            return make_image_block(content_nodes[0], media_info)
        return make_paragraph_block(node.decode_contents())
    if node.name and node.name.startswith("h"):
        try:
            level = int(node.name[1])
        except (ValueError, IndexError):
            level = 2
        return make_heading_block(level, node.decode_contents())
    if node.name in ("ul", "ol"):
        ordered = node.name == "ol"
        return make_list_block(node, ordered)
    if node.name == "blockquote":
        inner = "".join(str(child) for child in node.contents)
        return f"<!-- wp:quote -->\n<blockquote class=\"wp-block-quote\">{inner}</blockquote>\n<!-- /wp:quote -->"
    if node.name == "pre":
        inner = node.decode_contents()
        return f"<!-- wp:code -->\n<pre class=\"wp-block-code\"><code>{inner}</code></pre>\n<!-- /wp:code -->"
    if node.name == "img":
        return make_image_block(node, media_info)
    return node.decode()


def _is_whitespace(node: Union[Tag, NavigableString]) -> bool:
    return isinstance(node, NavigableString) and not node.strip()


def make_paragraph_block(inner_html: str) -> str:
    return f"<!-- wp:paragraph -->\n<p>{inner_html}</p>\n<!-- /wp:paragraph -->"


def make_heading_block(level: int, inner_html: str) -> str:
    attrs = json.dumps({"level": level}, ensure_ascii=False)
    return f"<!-- wp:heading {attrs} -->\n<h{level}>{inner_html}</h{level}>\n<!-- /wp:heading -->"


def make_list_block(node: Tag, ordered: bool) -> str:
    items_html = "".join(str(child) for child in node.contents)
    attrs = json.dumps({"ordered": ordered}, ensure_ascii=False)
    tag = "ol" if ordered else "ul"
    return f"<!-- wp:list {attrs} -->\n<{tag}>{items_html}</{tag}>\n<!-- /wp:list -->"


def make_image_block(img_tag: Tag, media_info: Dict[str, dict]) -> Optional[str]:
    src = img_tag.get("src")
    if not src:
        return None
    info = media_info.get(src, {})
    attrs: Dict[str, Union[str, int]] = {"sizeSlug": "full", "linkDestination": "none"}
    media_id = info.get("id")
    if media_id is not None:
        attrs["id"] = media_id
    alt_text = img_tag.get("alt", "") or info.get("alt", "")
    escaped_alt = html.escape(alt_text or "")
    figcaption = f"<figcaption>{escaped_alt}</figcaption>" if escaped_alt else ""
    img_html = f"<img src=\"{src}\" alt=\"{escaped_alt}\"/>"
    attrs_json = json.dumps(attrs, ensure_ascii=False)
    return (
        f"<!-- wp:image {attrs_json} -->\n"
        f"<figure class=\"wp-block-image size-full\">{img_html}{figcaption}</figure>\n"
        f"<!-- /wp:image -->"
    )


def convert_markdown_to_html(markdown_text: str) -> str:
    return markdown.markdown(markdown_text, extensions=["extra"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload markdown or HTML article to WordPress.")
    
    # 相互排他的なグループ：markdownまたはhtmlのいずれか一つ
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--markdown",
        help="Path to the markdown file to upload.",
    )
    input_group.add_argument(
        "--html",
        help="Path to the HTML file to upload.",
    )
    
    parser.add_argument(
        "--status",
        default="draft",
        choices=("draft", "publish"),
        help="WordPress post status (default: draft).",
    )
    parser.add_argument(
        "--category-name",
        default=DEFAULT_CATEGORY,
        help="Target category name (default: %(default)s).",
    )
    parser.add_argument(
        "--parent-category",
        default=DEFAULT_PARENT_CATEGORY,
        help="Parent category name used for disambiguation (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-title",
        action="store_true",
        help="Do not send the H1 as the WordPress title.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    # ファイルパスの決定
    if args.markdown:
        article_path = Path(args.markdown)
        file_type = "markdown"
    elif args.html:
        article_path = Path(args.html)
        file_type = "html"
    else:
        raise SystemExit("Either --markdown or --html must be specified.")
    
    if not article_path.exists():
        raise SystemExit(f"{file_type.capitalize()} file not found: {article_path}")

    wp_base = os.environ.get("WP_BASE_URL")
    wp_user = os.environ.get("WP_USERNAME")
    wp_pass = os.environ.get("WP_APP_PASSWORD")
    if not all([wp_base, wp_user, wp_pass]):
        raise SystemExit("WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD must be set in the environment.")

    # ファイル内容の読み込み
    file_content = article_path.read_text(encoding="utf-8")
    
    # ファイル形式に応じた処理
    if file_type == "markdown":
        # Markdownファイルの処理（既存のロジック）
        title = None if args.skip_title else extract_title_from_markdown(file_content)
        
        # 既存の改善済みHTMLファイルがある場合はそれを使用
        html_path = article_path.parent / "article.html"
        if html_path.exists():
            print(f"Using existing HTML file: {html_path}")
            full_html = html_path.read_text(encoding="utf-8")
            # HTMLファイルからbody部分を抽出
            soup = BeautifulSoup(full_html, "html.parser")
            body_tag = soup.find("body")
            if body_tag:
                html_content = str(body_tag.decode_contents())
            else:
                # bodyタグがない場合はそのまま使用
                html_content = full_html
        else:
            print("No HTML file found, converting from Markdown...")
            markdown_body = remove_leading_title(file_content)
            html_content = convert_markdown_to_html(markdown_body)
        
        images = find_local_images_from_markdown(file_content, article_path)
        
    else:  # HTML file
        # HTMLファイルの処理
        title = None if args.skip_title else extract_title_from_html(file_content)
        
        # HTMLファイルからbody部分を抽出（必要に応じて）
        soup = BeautifulSoup(file_content, "html.parser")
        body_tag = soup.find("body")
        if body_tag:
            html_content = str(body_tag.decode_contents())
        else:
            # bodyタグがない場合はそのまま使用
            html_content = file_content
            
        # h1タグをコンテンツから除去（WordPressのタイトル欄で使用するため）
        html_content = remove_h1_from_html(html_content)
        
        # プレースホルダー画像を含むfigureタグを除去
        html_content = remove_placeholder_figures(html_content)
        
        images = find_local_images_from_html(file_content, article_path)

    uploader = WordPressUploader(base_url=wp_base, username=wp_user, password=wp_pass)
    category_ids: List[int] = []
    if args.parent_category:
        parent_id = uploader.resolve_category_id_by_name(args.parent_category)
        category_ids.append(parent_id)
    child_id = uploader.resolve_category_id(args.category_name, args.parent_category)
    if child_id not in category_ids:
        category_ids.append(child_id)

    replacements: Dict[str, str] = {}
    media_info: Dict[str, dict] = {}
    featured_media_id: Optional[int] = None
    
    for i, image in enumerate(images):
        media = uploader.upload_media(image)
        remote_url = media["source_url"]
        media_id = media.get("id")
        
        # 最初の画像をアイキャッチに設定
        if i == 0 and media_id:
            featured_media_id = media_id
            print(f"Set as featured image: {image.rel_path}")
        
        replacements[image.rel_path] = remote_url
        media_info[remote_url] = {
            "id": media_id,
            "alt": image.alt_text,
        }
        print(f"Uploaded {image.rel_path} -> {remote_url}")

    html_with_remote = replace_image_urls(html_content, replacements)
    block_content = convert_html_to_blocks(html_with_remote, media_info)
    post = uploader.create_post(title=title, content=block_content, categories=category_ids, status=args.status, featured_media_id=featured_media_id)
    print(f"Created post ID {post['id']} at {post.get('link')}")
    if featured_media_id:
        print(f"Featured image set: media ID {featured_media_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

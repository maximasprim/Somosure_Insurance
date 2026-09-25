"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";

interface Category {
  id: string;
  slug: string;
  name: string;
}

interface ContentItem {
  id: string;
  slug: string;
  title: string;
  body: string;
  category_id: string | null;
  is_published: boolean;
}

interface Faq {
  id: string;
  question: string;
  answer: string;
  category_id: string | null;
  display_order: number;
  is_published: boolean;
}

const selectClass =
  "rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";
const textareaClass =
  "w-full rounded-control border border-neutral-border bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-deep/40 focus:border-brand-deep";

const emptyContentForm = { id: "", slug: "", title: "", body: "", category_id: "", is_published: false };
const emptyFaqForm = { id: "", question: "", answer: "", category_id: "", display_order: 0, is_published: true };

export default function AdminContentPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [contentForm, setContentForm] = useState(emptyContentForm);
  const [faqForm, setFaqForm] = useState(emptyFaqForm);
  const [savingContent, setSavingContent] = useState(false);
  const [savingFaq, setSavingFaq] = useState(false);

  async function loadAll() {
    try {
      const [cats, contentList, faqList] = await Promise.all([
        api.get<Category[]>("/api/v1/content/categories"),
        api.get<ContentItem[]>("/api/v1/admin/content"),
        api.get<Faq[]>("/api/v1/admin/content/faqs"),
      ]);
      setCategories(cats);
      setContent(contentList);
      setFaqs(faqList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load content");
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleSaveContent() {
    if (!contentForm.title.trim() || !contentForm.slug.trim() || !contentForm.body.trim()) return;
    setSavingContent(true);
    setError(null);
    try {
      if (contentForm.id) {
        await api.patch(`/api/v1/admin/content/${contentForm.id}`, {
          title: contentForm.title,
          body: contentForm.body,
          is_published: contentForm.is_published,
        });
      } else {
        await api.post("/api/v1/admin/content", {
          slug: contentForm.slug,
          title: contentForm.title,
          body: contentForm.body,
          category_id: contentForm.category_id || null,
          is_published: contentForm.is_published,
        });
      }
      setContentForm(emptyContentForm);
      loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save content");
    } finally {
      setSavingContent(false);
    }
  }

  async function togglePublishContent(item: ContentItem) {
    await api.patch(`/api/v1/admin/content/${item.id}`, { is_published: !item.is_published });
    loadAll();
  }

  async function deleteContent(id: string) {
    await api.del(`/api/v1/admin/content/${id}`);
    loadAll();
  }

  async function handleSaveFaq() {
    if (!faqForm.question.trim() || !faqForm.answer.trim()) return;
    setSavingFaq(true);
    setError(null);
    try {
      const payload = {
        question: faqForm.question,
        answer: faqForm.answer,
        category_id: faqForm.category_id || null,
        display_order: Number(faqForm.display_order) || 0,
        is_published: faqForm.is_published,
      };
      if (faqForm.id) {
        await api.patch(`/api/v1/admin/content/faqs/${faqForm.id}`, payload);
      } else {
        await api.post("/api/v1/admin/content/faqs", payload);
      }
      setFaqForm(emptyFaqForm);
      loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save FAQ");
    } finally {
      setSavingFaq(false);
    }
  }

  async function togglePublishFaq(faq: Faq) {
    await api.patch(`/api/v1/admin/content/faqs/${faq.id}`, { is_published: !faq.is_published });
    loadAll();
  }

  async function deleteFaq(id: string) {
    await api.del(`/api/v1/admin/content/faqs/${id}`);
    loadAll();
  }

  return (
    <main className="mx-auto max-w-8xl px-6 py-12">
      <h1 className="text-2xl font-bold">Content & FAQs</h1>
      <p className="mt-1 text-ink-soft">Manage the educational articles and FAQ entries shown publicly on the site.</p>

      {error && <p className="mt-4 rounded-control bg-status-error/10 px-4 py-2 text-sm text-status-error">{error}</p>}

      {/* --- FAQs --- */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold">FAQs</h2>
        <Card className="mt-3 flex flex-col gap-3">
          <div className="grid gap-3">
            <Input label="Question" value={faqForm.question} onChange={(e) => setFaqForm({ ...faqForm, question: e.target.value })} />
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink">Answer</label>
              <textarea
                className={textareaClass}
                rows={3}
                value={faqForm.answer}
                onChange={(e) => setFaqForm({ ...faqForm, answer: e.target.value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-ink">Category</label>
                <select
                  className={selectClass}
                  value={faqForm.category_id}
                  onChange={(e) => setFaqForm({ ...faqForm, category_id: e.target.value })}
                >
                  <option value="">None</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Display order"
                type="number"
                value={faqForm.display_order}
                onChange={(e) => setFaqForm({ ...faqForm, display_order: Number(e.target.value) })}
              />
              <label className="flex items-center gap-2 self-end pb-2 text-sm">
                <input
                  type="checkbox"
                  checked={faqForm.is_published}
                  onChange={(e) => setFaqForm({ ...faqForm, is_published: e.target.checked })}
                />
                Published
              </label>
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSaveFaq} disabled={savingFaq}>
              {faqForm.id ? "Save changes" : "Add FAQ"}
            </Button>
            {faqForm.id && (
              <Button variant="ghost" onClick={() => setFaqForm(emptyFaqForm)}>
                Cancel
              </Button>
            )}
          </div>
        </Card>

        <div className="mt-4 flex flex-col gap-2">
          {faqs.map((f) => (
            <Card key={f.id} className="flex flex-wrap items-center justify-between gap-3">
              <div className="max-w-lg">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{f.question}</h3>
                  {!f.is_published && <Badge tone="error">Draft</Badge>}
                </div>
                <p className="mt-1 text-sm text-ink-soft">{f.answer}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setFaqForm({ ...f, category_id: f.category_id ?? "" })}>
                  Edit
                </Button>
                <Button variant="ghost" onClick={() => togglePublishFaq(f)}>
                  {f.is_published ? "Unpublish" : "Publish"}
                </Button>
                <Button variant="ghost" onClick={() => deleteFaq(f.id)}>
                  Delete
                </Button>
              </div>
            </Card>
          ))}
          {faqs.length === 0 && <p className="text-ink-soft">No FAQs yet.</p>}
        </div>
      </section>

      {/* --- Articles --- */}
      <section className="mt-12">
        <h2 className="text-lg font-semibold">Articles</h2>
        <Card className="mt-3 flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Title" value={contentForm.title} onChange={(e) => setContentForm({ ...contentForm, title: e.target.value })} />
            <Input
              label="Slug"
              value={contentForm.slug}
              disabled={!!contentForm.id}
              onChange={(e) => setContentForm({ ...contentForm, slug: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-ink">Body</label>
            <textarea
              className={textareaClass}
              rows={5}
              value={contentForm.body}
              onChange={(e) => setContentForm({ ...contentForm, body: e.target.value })}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-ink">Category</label>
              <select
                className={selectClass}
                value={contentForm.category_id}
                disabled={!!contentForm.id}
                onChange={(e) => setContentForm({ ...contentForm, category_id: e.target.value })}
              >
                <option value="">None</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 self-end pb-2 text-sm">
              <input
                type="checkbox"
                checked={contentForm.is_published}
                onChange={(e) => setContentForm({ ...contentForm, is_published: e.target.checked })}
              />
              Published
            </label>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSaveContent} disabled={savingContent}>
              {contentForm.id ? "Save changes" : "Add article"}
            </Button>
            {contentForm.id && (
              <Button variant="ghost" onClick={() => setContentForm(emptyContentForm)}>
                Cancel
              </Button>
            )}
          </div>
        </Card>

        <div className="mt-4 flex flex-col gap-2">
          {content.map((c) => (
            <Card key={c.id} className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{c.title}</h3>
                  {!c.is_published && <Badge tone="error">Draft</Badge>}
                </div>
                <p className="mt-1 text-xs text-ink-soft">/{c.slug}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setContentForm({ ...c, category_id: c.category_id ?? "" })}>
                  Edit
                </Button>
                <Button variant="ghost" onClick={() => togglePublishContent(c)}>
                  {c.is_published ? "Unpublish" : "Publish"}
                </Button>
                <Button variant="ghost" onClick={() => deleteContent(c.id)}>
                  Delete
                </Button>
              </div>
            </Card>
          ))}
          {content.length === 0 && <p className="text-ink-soft">No articles yet.</p>}
        </div>
      </section>
    </main>
  );
}

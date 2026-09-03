import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import { FontSize, TextStyle } from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import FontFamily from "@tiptap/extension-font-family";
import TextAlign from "@tiptap/extension-text-align";

type Props = { value: string; onChange: (html: string, text: string) => void };
const tool = (active = false) => `rounded px-2 py-1 text-sm ${active ? "bg-blue-100 text-blue-800" : "hover:bg-slate-100"}`;

export function MailRichTextEditor({ value, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit, Underline, TextStyle, FontSize, Color, FontFamily, TextAlign.configure({ types: ["heading", "paragraph"] })],
    content: value,
    onUpdate: ({ editor: instance }) => onChange(instance.getHTML(), instance.getText()),
    editorProps: { attributes: { class: "min-h-64 px-4 py-3 text-sm leading-7 outline-none" } },
  });
  useEffect(() => { if (editor && value !== editor.getHTML()) editor.commands.setContent(value, { emitUpdate: false }); }, [editor, value]);
  if (!editor) return null;
  const run = (callback: () => void) => () => callback();
  return <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"><div className="flex flex-wrap items-center gap-1 border-b bg-slate-50 px-2 py-1.5"><select aria-label="字体" className="rounded border-0 bg-transparent text-xs" onChange={(e) => editor.chain().focus().setFontFamily(e.target.value).run()} defaultValue=""><option value="">字体</option><option value="Arial">Arial</option><option value="Microsoft YaHei">微软雅黑</option><option value="Georgia">Georgia</option></select><select aria-label="字号" className="rounded border-0 bg-transparent text-xs" onChange={(e) => editor.chain().focus().setFontSize(e.target.value).run()} defaultValue=""><option value="">字号</option><option value="12px">小</option><option value="14px">正常</option><option value="18px">大</option></select><span className="mx-1 h-5 border-l" /><button type="button" aria-label="粗体" className={tool(editor.isActive("bold"))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().toggleBold().run())}><b>B</b></button><button type="button" aria-label="斜体" className={tool(editor.isActive("italic"))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().toggleItalic().run())}><i>I</i></button><button type="button" aria-label="下划线" className={tool(editor.isActive("underline"))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().toggleUnderline().run())}><u>U</u></button><input aria-label="文字颜色" type="color" className="h-7 w-8" onChange={(e) => editor.chain().focus().setColor(e.target.value).run()} /><span className="mx-1 h-5 border-l" /><button type="button" aria-label="项目符号" className={tool(editor.isActive("bulletList"))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().toggleBulletList().run())}>☷</button><button type="button" aria-label="编号列表" className={tool(editor.isActive("orderedList"))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().toggleOrderedList().run())}>☰</button><button type="button" aria-label="左对齐" className={tool(editor.isActive({ textAlign: "left" }))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().setTextAlign("left").run())}>≡</button><button type="button" aria-label="居中" className={tool(editor.isActive({ textAlign: "center" }))} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().setTextAlign("center").run())}>≡</button><button type="button" aria-label="插入链接" className={tool()} onMouseDown={(e) => e.preventDefault()} onClick={() => { const href = window.prompt("输入链接"); if (href) editor.chain().focus().setLink({ href }).run(); }}>🔗</button><button type="button" aria-label="清除格式" className={tool()} onMouseDown={(e) => e.preventDefault()} onClick={run(() => editor.chain().focus().unsetAllMarks().clearNodes().run())}>⌫</button></div><EditorContent editor={editor} /></div>;
}

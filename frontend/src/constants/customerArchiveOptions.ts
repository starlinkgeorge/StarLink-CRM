/**
 * Exact list validation choices from the "客户档案表" sheet in
 * George外贸工作表.xlsx. The empty option is intentional: every source
 * validation permits blank values in the workbook.
 */
export const customerArchiveOptions = {
  source: ["询盘", "RFQ", "访客营销", "中国制造", "FB", "INS", "领英", "开发信", "WhatsApp", "客户介绍"],
  customerType: ["幼儿园", "网店", "实体店", "个人"],
  interestedProduct: ["家具", "蒙氏", "木制玩具", "皮克勒", "学习塔", "其它"],
  customerLevelValue: [1, 2, 3, 4],
  customerSize: [1, 2, 3, 4],
  followupStage: ["新开发未回复", "新开发已回复", "已报价", "已采购样品", "已成交", "已复购", "冷客户"],
  responseStatus: ["是", "否"],
} as const;

from django.db.models import Q, Case, When, QuerySet
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_cohere.rerank import CohereRerank
from pgvector.django import CosineDistance


def hybrid_search_with_rerank(
    queryset: QuerySet,
    vector_field_name: str,
    text_field_name: str,
    original_question: str
) -> QuerySet:
    # 1. Extract keywords with OpenAI
    prompt = ChatPromptTemplate.from_template(
        "Extract relevant keywords from the following user question. "
        "Return them as a comma-separated list. "
        "User Question: {question}"
    )
    model = ChatOpenAI(model="gpt-4o")
    parser = StrOutputParser()
    chain = prompt | model | parser
    keywords_str = chain.invoke({"question": original_question})
    keywords = [keyword.strip() for keyword in keywords_str.split(',') if keyword.strip()]

    # 2. Keyword-based search (Fuzzy search) - 在原始 queryset 上進行
    keyword_results = []
    if keywords:
        keyword_query = Q()
        for keyword in keywords:
            keyword_query |= Q(**{f"{text_field_name}__icontains": keyword})
        keyword_results = list(queryset.filter(keyword_query)[:10])

    # 3. Vector-based search - 在原始 queryset 上進行
    question_embeddings = OpenAIEmbeddings(model="text-embedding-3-small").embed_query(original_question)
    vector_results = list(queryset.annotate(
        distance=CosineDistance(vector_field_name, question_embeddings)
    ).order_by("distance")[:10])

    # 4. Combine and deduplicate results
    combined_results = []
    seen_ids = set()

    # 添加調試信息
    print(f"關鍵字搜尋結果數量: {len(keyword_results)}")
    print(f"向量搜尋結果數量: {len(vector_results)}")

    # 合併兩個結果集並去重
    for result in keyword_results + vector_results:
        if result.id not in seen_ids:
            combined_results.append(result)
            seen_ids.add(result.id)

    print(f"合併去重後結果數量: {len(combined_results)}")

    # 5. Rerank using Cohere
    reranker = CohereRerank(
        model="rerank-multilingual-v3.0",
        top_n=5
    )

    docs_to_rerank = [
        Document(page_content=getattr(res, text_field_name), metadata={"id": res.id})
        for res in combined_results
    ]

    reranked_docs = reranker.compress_documents(
        documents=docs_to_rerank,
        query=original_question
    )

    print(f"Rerank 後結果數量: {len(reranked_docs)}")

    # 6. 建立最終排序結果
    sorted_ids = [doc.metadata["id"] for doc in reranked_docs]
    preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(sorted_ids)])

    final_queryset = queryset.model.objects.filter(pk__in=sorted_ids).order_by(preserved_order)
    
    print(f"最終結果數量: {final_queryset.count()}")
    return final_queryset 
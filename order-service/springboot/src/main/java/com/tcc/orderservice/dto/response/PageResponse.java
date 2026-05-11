package com.tcc.orderservice.dto.response;

import java.util.ArrayList;
import java.util.List;

public class PageResponse<T> {

	private List<T> content;
	private long totalElements;
	private int totalPages;
	private int currentPage;
	private int pageSize;

	public PageResponse() {
		this.content = new ArrayList<>();
	}

	public PageResponse(List<T> content,
			long totalElements,
			int totalPages,
			int currentPage,
			int pageSize) {
		this.content = content == null ? new ArrayList<>() : new ArrayList<>(content);
		this.totalElements = totalElements;
		this.totalPages = totalPages;
		this.currentPage = currentPage;
		this.pageSize = pageSize;
	}

	public List<T> getContent() {
		if (this.content == null) {
			this.content = new ArrayList<>();
		}

		return content;
	}

	public void setContent(List<T> content) {
		this.content = content == null ? new ArrayList<>() : new ArrayList<>(content);
	}

	public long getTotalElements() {
		return totalElements;
	}

	public void setTotalElements(long totalElements) {
		this.totalElements = totalElements;
	}

	public int getTotalPages() {
		return totalPages;
	}

	public void setTotalPages(int totalPages) {
		this.totalPages = totalPages;
	}

	public int getCurrentPage() {
		return currentPage;
	}

	public void setCurrentPage(int currentPage) {
		this.currentPage = currentPage;
	}

	public int getPageSize() {
		return pageSize;
	}

	public void setPageSize(int pageSize) {
		this.pageSize = pageSize;
	}
}

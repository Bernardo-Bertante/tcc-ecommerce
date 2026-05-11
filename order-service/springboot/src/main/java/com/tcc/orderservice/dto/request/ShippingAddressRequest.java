package com.tcc.orderservice.dto.request;

public class ShippingAddressRequest {

	private String zipCode;
	private String street;
	private String number;
	private String complement;
	private String city;
	private String state;

	public ShippingAddressRequest() {
	}

	public ShippingAddressRequest(String zipCode,
			String street,
			String number,
			String complement,
			String city,
			String state) {
		this.zipCode = zipCode;
		this.street = street;
		this.number = number;
		this.complement = complement;
		this.city = city;
		this.state = state;
	}

	public String getZipCode() {
		return zipCode;
	}

	public void setZipCode(String zipCode) {
		this.zipCode = zipCode;
	}

	public String getStreet() {
		return street;
	}

	public void setStreet(String street) {
		this.street = street;
	}

	public String getNumber() {
		return number;
	}

	public void setNumber(String number) {
		this.number = number;
	}

	public String getComplement() {
		return complement;
	}

	public void setComplement(String complement) {
		this.complement = complement;
	}

	public String getCity() {
		return city;
	}

	public void setCity(String city) {
		this.city = city;
	}

	public String getState() {
		return state;
	}

	public void setState(String state) {
		this.state = state;
	}
}

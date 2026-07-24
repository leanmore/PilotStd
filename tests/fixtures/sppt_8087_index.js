//搜索
function listSearch(kw){
	var keyword='';
	if(kw!=''){
		keyword=kw;
	}else{
		keyword=document.getElementById("keyword").value;
		if(keyword==''){
			alert("请输入要搜索的关键词！");
			return false;
		}
	}
	form1.keyword.value=keyword;
	form1.task.value='listSearch_Website';
	form1.action='/db';
	form1.submit();
}
//查看信息
function info(num_tn,guid){
	form1.num_tn.value=num_tn;
	form1.guid.value=guid;
	form1.task.value='viewSearchInfo';
	form1.action='/db';
	form1.target='_blank';
	form1.submit();
}
//高级搜索
function advancedSearch(){
	form1.task.value='listAdvancedSearch_Website';
	form1.action='/db';
	form1.submit();
}
//地方标准(公众查询)高级搜索
function advancedSearchDfPub(){
	form1.task.value='listAdvancedSearch_df_pub';
	form1.action='/db';
	form1.submit();
}
//enter事件
function scheck(){
	if (event.keyCode == 13){ 
		listSearch('');
	}
}
//友情链接
function yqlj(url){
	form1.target='_blank';
	form1.action="/db?task=yqlj_Link&url="+url;
	form1.submit();
}
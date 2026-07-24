//显示信息
function showInfo(obj){
	if(obj.value=="请输入要搜索的关键词"){
		obj.value='';
		obj.style.color='black';
		var text = document.getElementById('keyword');
		text.focus(); 
		var text = text.createTextRange();
		text.collapse(false); 
		text.select(); 
	}
 }
//查看信息
function info(num_tn,guid){
	form1.num_tn.value=num_tn;
	form1.guid.value=guid;
	form1.task.value='viewSearchInfo';
	form1.target='_blank';
	form1.action='/db';
	form1.submit();
}
//高级查询
function openAdvancedSearch(){
	form1.query.value='';
	form1.task.value='listAdvancedSearch_Website';
	form1.target='_blank';
	form1.action='/db';
	form1.submit();
}
//地方标准(公众查询)高级搜索
function openAdvancedSearchDfPub(){
	form1.query.value='';
	form1.task.value='listAdvancedSearch_df_pub';
	form1.target='_blank';
	form1.action='/db';
	form1.submit();
}
//搜索
function listSearch(kw){
	var keyword='';
	if(kw!=''){
		document.getElementById("keyword").value=kw;
	}else{
		keyword=document.getElementById("keyword").value;
		if(keyword==''){
			alert("请输入要搜索的关键词！");
			return false;
		}
	}
	form1.target='';
	form1.pageIndex.value=1;
	form1.action='/db';
	form1.task.value='listSearch_Website';
	form1.submit();
}
//enter事件
function scheck(kw){
	if (event.keyCode == 13){
		listSearch(kw);
	}
}
//预览
function preview(fact_name){
	form1.fact_name.value=fact_name;
	form1.target='_blank';
	form1.task.value="view_Document";
	form1.action='/db';
	form1.submit();
}
//下载
function load(guid){
	form1.target='';
	form1.file_guid.value=guid;
	form1.task.value='d_p';
	form1.action='/cfsa_aiguo';
	form1.submit();
}
//翻页
function turnPage(pageIndex,task){
	form1.target='';
	form1.query.value="yes";
	form1.task.value=task;
	form1.pageIndex.value=pageIndex;
	form1.action='/db';
	form1.submit();
}
//访问首页
function index(){
	form1.target='';
	form1.task.value='index';
	form1.action='/db';
	form1.submit();
}
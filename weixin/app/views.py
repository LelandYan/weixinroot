from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
import requests
import time
import re
import json

CTIME = None
QCODE = None
TIP = 1
TICKET_DICT = {}
USER_INIT_DICT = {}
ALL_COOKIE_DICT = {}


# Create your views here.
def login(request):
    """
    获取二维码
    :param request:
    :return:
    """
    global CTIME
    CTIME = time.time()
    responses = requests.get(
        url='https://login.wx.qq.com/jslogin?appid=wx782c26e4c19acffb&fun=new&lang=zh_CN&_=%s' % CTIME
    )
    v = re.findall('uuid = "(.*)";', responses.text)
    global QCODE
    QCODE = v[0]
    return render(request, 'login.html', {'qcode': QCODE})


def check_login(request):
    """
    监听用于是否扫码，是否点击确认
    :param request:
    :return:
    """
    global TIP
    ret = {'code': 408, 'data': None}
    r1 = requests.get(
        url='https://login.wx.qq.com/cgi-bin/mmwebwx-bin/login?loginicon=true&uuid=%s&tip=%s&r=1749695388&_=%s' % (
            QCODE, TIP, CTIME)
    )
    if 'window.code=408' in r1.text:
        print('无人扫')
        return JsonResponse(ret)
    elif 'window.code=201' in r1.text:
        ret['code'] = 201
        TIP = 0
        avatar = re.findall("window.userAvatar = '(.*)';", r1.text)[0]
        ret['data'] = avatar
        return JsonResponse(ret)
    elif 'window.code=200' in r1.text:
        """
        window.code=200;
        window.redirect_uri="https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxnewloginpage?ticket=AcXy5ztnQJ2IpDYRovCJl1YW@qrticket_0&uuid=IaOl9pugOw==&lang=zh_CN&scan=1535854116";

        """
        ALL_COOKIE_DICT.update(r1.cookies.get_dict())
        redirect_url = re.findall('window.redirect_uri="(.*)";', r1.text)[0]
        redirect_url += '&fun=new&version=v2'
        r2 = requests.get(
            url=redirect_url
        )
        ALL_COOKIE_DICT.update(r2.cookies.get_dict())
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r2.text, 'html.parser')
        for tag in soup.find('error').children:
            TICKET_DICT[tag.name] = tag.get_text()
        ret['code'] = 200
        return JsonResponse(ret)


def user(request):
    """
    个人主页
    :param request:
    :return:
    """
    # 获取用户信息
    get_url_info_data = {
        'BaseRequest': {
            'DeviceID': "e128446397750611",
            'Sid': TICKET_DICT['wxsid'],
            'Skey': TICKET_DICT['skey'],
            'Uin': TICKET_DICT['wxuin']
        }
    }
    get_user_info_url = 'https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxinit?r=1727545458&lang=zh_CN&pass_ticket=' + \
                        TICKET_DICT['pass_ticket']
    r3 = requests.post(
        url=get_user_info_url,
        json=get_url_info_data
    )
    r3.encoding = 'utf-8'
    user_init_dict = json.loads(r3.text)
    USER_INIT_DICT.update(user_init_dict)
    ALL_COOKIE_DICT.update(r3.cookies.get_dict())
    print(user_init_dict)
    return render(request, 'user.html', {'user_init_dict': user_init_dict})


def contact_list(request):
    """
    获取所有联系人
    :param request:
    :return:
    """
    """
    https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&pass_ticket=FsxKfNmCRdqgxY2TpCIIiUs8LXeIY3gkTa%252FJWytRfSxU%252BJSsntowCOwJo3vMhTu3&r=1536024124307&seq=0&skey=@crypt_30867e95_ad17bbaaae27fa8266bccccc752d94ef
    """
    ctime = str(time.time() * 1000)
    base_url = 'https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxgetcontact?lang=zh_CN&pass_ticket=%s&r=%s&seq=0&skey=%s'
    url = base_url % (TICKET_DICT['pass_ticket'], ctime, TICKET_DICT['skey'])
    response = requests.get(
        url=url,
        cookies=ALL_COOKIE_DICT
    )
    response.encoding = 'utf-8'
    contact_list_dict = json.loads(response.text)
    USER_INIT_DICT.update(contact_list_dict)
    for item in contact_list_dict['MemberList']:
        print(item['NickName'], item['UserName'])
    return render(request, 'contact_list.html', {"contact_list_dict": contact_list_dict})


def send_msg(request):
    """
    发送消息
    :param request:
    :return:
    """
    to_user = request.GET.get('toUser')
    msg = request.GET.get('msg')
    url = 'https://wx.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg?lang=zh_CN&pass_ticket=%s' % (TICKET_DICT['pass_ticket'])
    ctime = str(int(time.time() * 1000))
    post_dict = {
        'BaseRequest': {
            'DeviceID': "e128446397750611",
            'Sid': TICKET_DICT['wxsid'],
            'Skey': TICKET_DICT['skey'],
            'Uin': TICKET_DICT['wxuin']
        },
        'Msg': {
            'ClientMsgId': ctime,
            'Content': msg,
            'FromUserName': USER_INIT_DICT['User']['UserName'],
            'LocalID': ctime,
            'ToUserName': to_user.strip(),
            'Type': 1,
        },
        'Score': 0
    }
    print(post_dict)
    response = requests.post(
        url=url,
        data=bytes(json.dumps(post_dict, ensure_ascii=False), encoding='utf-8')
    )
    response.encoding = 'utf-8'
    contact_list_dict = json.loads(response.text)
    USER_INIT_DICT.update(contact_list_dict)
    print(response.text)
    return HttpResponse('ok')


def get_msg(request):
    """
    获取消息
    :param request:
    :return:
    """
    # 检查是否有消息到来
    # 若有消息到来window.synccheck={retcode:"0",selector:"2"}
    print('start....')
    print(USER_INIT_DICT)
    synckey_list = USER_INIT_DICT['SyncKey']['List']
    print(synckey_list)
    sync_list = []
    for item in synckey_list:
        temp = "%s_%s" % (item['Key'], item['Val'])
        sync_list.append(temp)
    synckey = "|".join(sync_list)
    #print(synckey)
    heads = {}
    heads['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
    r1 = requests.get(
        url='https://webpush.wx.qq.com/cgi-bin/mmwebwx-bin/synccheck',
        params={
            'r': str(int(time.time() * 1000)),
            'DeviceID': "e128446397750611",
            'Sid': TICKET_DICT['wxsid'],
            'Skey': TICKET_DICT['skey'],
            'Uin': TICKET_DICT['wxuin'],
            'synckey': synckey
        },
        cookies=ALL_COOKIE_DICT,
    )
    print(r1.text)
    print('end.....')
    return HttpResponse("123")

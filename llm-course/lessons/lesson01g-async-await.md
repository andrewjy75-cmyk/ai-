# 练习 03 补充专讲：async/await 到底是什么，为什么要这样写

> 学员是 Java 老手，本篇全程用 Java 类比，把 JS 的 async/await 和
> Python 的 async/await 一起讲透。末尾回答"要不要理解，还是公式套用"。

## 1. 先回答"数据格式"：reader.read() 返回什么

```javascript
const {done, value} = await reader.read();
```

这一行返回的不是 JSON，不是"message 那种结构化对象"，而是：

```javascript
{
  done: false,                    // false = 流还没结束，value 里有数据
  value: Uint8Array(比如 47 个字节)  // 原始字节！不是文字！
}
```

**网络只传字节**。服务端发来的 `data:杭州\n\n` 经过网络到浏览器，是 47 个字节（byte），
不是"杭州"这两个字。所以需要 `TextDecoder` 把字节翻译成文字——这就是前面
`const decoder = new TextDecoder(); decoder.decode(value)` 的用途。

最后一次读取时返回 `{done: true, value: undefined}`——表示服务器关连接了，流结束。

## 2. `const {done, value} = ...` 是什么语法？——解构（destructuring）

它不是"特殊接收方式"，而是**一次性从对象里拆出两个字段**的简写。等价于：

```javascript
const result = await reader.read();   // 先拿到整个对象
const done = result.done;             // 再逐个取字段
const value = result.value;
```

解构就是把这四行合并成一行的语法糖——"我要从这个对象里取出 done 和 value 两个键"。

**Java 类比**（如果 read() 返回一个 record/对象）：
```java
// Java 写法
var result = reader.read();
boolean done = result.done();
byte[] value = result.value();

// 概念上的"解构"= 声明时就同时拆出字段，少写两行取值代码
```

**Python 类比**（你更熟）：就是元组解包
```python
done, value = await reader.read()
```
Python 按位置拆，JS 按字段名拆，思想一样：**一步到位把容器里的东西取出来**。

## 3. 为什么要异步？—— JS 只有一个线程，卡住就是冻屏

这是理解一切的根基。**浏览器里的 JavaScript 是单线程的**——整个页面只有一个
"工作线程"在跑你的代码。它要是被某件事卡住，页面上的按钮、滚动、动画全部停摆。

想象 Java：请求网络时你可以放心 `response.getBody()`——阻塞就阻塞，反正线程池里
还有很多线程干别的。但 JS 只有一个线程，**没有别的线程可以顶班**。所以：

> JS 规定：**网络请求这种"耗时等待"的操作，一律不许同步阻塞**，只能异步。

这就引出了 Promise。

## 4. Promise：一张"取货单"

```javascript
const resp = fetch("/chat", {...});
// fetch 立刻返回，不等网络！
// 返回的是一个 Promise（取货单）："货到了我会通知你"
console.log(resp);   // Promise {<pending>} —— 不是数据！是张单子
```

`fetch` 发出请求后**立即返回**，不傻等。返回的 Promise 就是一张取货单：
货（服务器响应）到了之后，这张单子会"兑现"（resolve），把货交给你。

**Java 类比**：`CompletableFuture<T>`——提交任务立刻拿到一个 Future，
`future.get()` 才阻塞等结果。Promise ≈ Future。

## 5. await：把"异步的等"伪装成"同步的写"（关键！）

```javascript
const resp = await fetch("/chat", {...});
// 加了 await：在这"暂停"本函数，等货到了继续往下走
// resp 现在是真正的 Response 对象了
```

`await` 的作用：**暂停当前这个函数**（注意：不是暂停整个程序），等 Promise 兑现，
然后把"货"作为结果返回，继续往下执行。暂停期间，JS 事件循环去干别的活
（刷新界面、响应点击、处理别的请求），等货到了再回来接着跑。

**这就是为什么"看起来像同步代码，却不冻屏"**——await 是合作式暂停，
不是死等。像 Java 21 虚拟线程：你写阻塞风格的代码，运行时悄悄挂起换人干。

### 铁律：await 只能在 async 函数里用

```javascript
async function send() {        // 声明 async：这个函数内部可以用 await
    const resp = await fetch(...);   // ✅ 合法
    const {done, value} = await reader.read();   // ✅ 合法
}
```

`async` 是给函数盖的章："本函数体内允许使用 await"。反过来说，
**看到 await 却不在 async 函数里 → 语法错误**。这就是你代码里 `send()`
前面必须有 `async` 的原因。

### 整条链路拆给你看

```javascript
async function send() {
    // ① 发请求（异步，先拿单子）
    const resp = await fetch("/chat", {...});   // await 取货：真 Response
    // ② 拿流的读取器
    const reader = resp.body.getReader();
    // ③ 循环读流：每读一次要等网络送数据来 → 必须 await
    while (true) {
        const {done, value} = await reader.read();   // 等下一块字节
        if (done) break;                              // 服务器关连接了
        const text = decoder.decode(value);           // 字节 → 文字
        // ...拆 data: 前缀，拼进页面
    }
}
```

**每一处 await 都对应一次"要等网络"**：等响应头、等下一块流数据。
网络慢没关系——函数挂着，页面照样能点能滚，这就是异步的意义。

## 6. Python 的 async/await 是同一套思想

Python 的 `async def` + `await` 和 JS 完全同源（都是事件循环 + 协程）：

```python
async def chat(payload: dict):        # async def = JS 的 async function
    ...
```

你台阶 B/C 里的 `chat` 就是 `async def`——不过你函数里没有 await，
因为它只是把 StreamingResponse 返回出去，真正等网络发生在生成器里（同步跑）。
**FastAPI 允许同步 def**：如果函数里没有 await，写普通 def 也行，
FastAPI 会丢到线程池里跑，效果一样。初学不用纠结这个，记住：

> async def + await = "这个函数会等 I/O，等的时候把控制权交还事件循环"

## 7. 到底要不要理解？我的答案：理解到"够用层"，别钻牛角尖

**必须理解的**（不然后面 100% 会踩坑）：

1. **网络操作在 JS 里只能异步**——fetch 不加 await 拿到的是 Promise 不是数据，
   打印出来是 `Promise {<pending>}`。这是新手最经典的 bug
2. **await 只能在 async 函数里**，反之语法错误
3. **每处 await = 一处"等网络"**；解构 `{done, value}` 只是取字段的简写

**不需要理解的**（先跳过，等真遇到再补）：
- 事件循环底层实现、宏任务微任务队列、Promise 的 then/catch 链式细节
- Python asyncio 的事件循环原理

**判断自己够不够用的标准**：看到 `fetch(...)` 能条件反射知道"得 await"；
看到报错 "await is only valid in async function" 能立刻知道去哪加 async；
看到 `Promise {<pending>}` 能知道忘了 await。**这三点会了，公式化套用完全没问题。**

## 速查卡（背下来）

| 现象 | 原因 | 修法 |
|---|---|---|
| 打印出 `Promise {<pending>}` | 忘了 await | 加 await |
| 报错 "await is only valid in async function" | await 写在非 async 函数里 | 给函数加 async |
| 页面卡死不动 | 代码里有同步阻塞等待（比如用了老式 XMLHttpRequest 同步模式） | 改用 fetch + await |
| 数据是乱码 | 忘了 TextDecoder 解码 | decode(value) |
